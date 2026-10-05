import io
import logging
import zipfile
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_sat_client import (
    SAT_SUCCESS_STATUS_CODE,
)

_logger = logging.getLogger(__name__)

SAT_EXPIRED_CODES = {'5007'}

SAT_MAX_PROCESS_WAIT_DAYS = 15   # in_process: SAT still generating the package
SAT_MAX_DOWNLOAD_WAIT_DAYS = 4   # in_download: package ready but not downloaded (72h + margin)
SAT_MAX_UNPACK_WAIT_DAYS = 2     # unpacking: to avoid have work stucked.

# Minutes a request waits before a scheduled action asks SAT about it again.
# This is intended to work as a hard cap on how often the request is retried.
STATE_RETRY_DELAY = {
    'in_process_at_sat': 60,   # SAT takes its time building a package; asking sooner tells us nothing
    'in_download': 30,         # a package only lives 72h, so this one is worth chasing harder
}

UNPACK_BATCH_SIZE = 1000
DOC_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB absolute max per file

REQUEST_TYPE_SELECTION = frozenset([
    ("folio", "Folio"),
    ("batch_issued", "CFDI (Issued)"),
    ("batch_received", "CFDI (Received)"),
])
REQUEST_TYPE_DESCRIPTION = (
    "Scope of the download request sent to the SAT.\n"
    "- Folio: a single CFDI, identified by its Fiscal Folio.\n"
    "- CFDI (Issued): all CFDI issued by this company within a date range.\n"
    "- CFDI (Received): all CFDI issued to this company within a date range."
)

RECEIPT_TYPE_SELECTION = frozenset([
    ("I", "I (Income)"),
    ("E", "E (Credit Note)"),
])
RECEIPT_TYPE_DESCRIPTION = (
    "Kind of CFDI to download, and the document it becomes in Odoo.\n"
    "- I (Income): a customer invoice for an Issued request, a vendor bill for a Received request.\n"
    "- E (Credit Note): a customer credit note for an Issued request, a vendor credit note for a"
    " Received request."
)


class L10n_Mx_EdiCfdiRequest(models.Model):
    _name = "l10n_mx_edi.cfdi.request"
    _description = "CFDI Request"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True, readonly=True,
        default=lambda self: self.env.company,
    )
    request_type = fields.Selection(
        selection=list(REQUEST_TYPE_SELECTION),
        readonly=True, required=True,
        help=REQUEST_TYPE_DESCRIPTION,
    )
    state = fields.Selection(
        selection=[
            ("in_process_at_sat", "In Process at SAT"),
            ("in_download", "Ready for Download"),
            ("unpacking", "Unpacking"),
            ("done", "Done"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
        ],
        readonly=True, copy=False,
        required=True,
        help="How far the request has got.\n"
             "- In Process at SAT: SAT accepted the request and is building the package.\n"
             "- Ready for Download: the package is ready to download at SAT.\n"
             "- Unpacking: the package is downloaded, documents are being extracted in the background.\n"
             "- Done: Package completed extracting documents.\n"
             "- Rejected: SAT refused the request.\n"
             "- Expired: Request/Package expired.",
    )
    receipt_type = fields.Selection(
        selection=list(RECEIPT_TYPE_SELECTION),
        readonly=True,
        string="Receipt Type",
        help=RECEIPT_TYPE_DESCRIPTION,
    )
    emission_date_from = fields.Date(readonly=True, string="From")
    emission_date_to = fields.Date(readonly=True, string="To")
    cfdi_uuid = fields.Char(
        string="CFDI UUID",
        readonly=True,
        help="The Fiscal Folio of the document to be requested in case of a folio request",
    )
    request_uuid = fields.Char(
        string="Request UUID",
        readonly=True, copy=False,
    )
    package_uuid = fields.Char(
        string="Package UUID",
        readonly=True,
        copy=False,
    )
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        readonly=True, copy=False,
    )
    l10n_mx_edi_document_ids = fields.One2many(
        comodel_name="l10n_mx_edi.document",
        inverse_name="cfdi_request_id",
        readonly=True,
    )
    message = fields.Text(readonly=True, copy=False, string="Info")
    is_retryable = fields.Boolean(
        string="Retryable",
        readonly=True, copy=False, default=True,
        help="Whether a scheduled action may still process this request.",
    )
    ready_at = fields.Datetime(
        readonly=True, copy=False,
        help="Time the package became ready for download.",
    )
    last_cron_attempt = fields.Datetime(
        string="Last Attempt",
        readonly=True, copy=False, index=True,
        help="Time a scheduled action last processed this request.",
    )
    unpacked_count = fields.Integer(
        string="Documents Unpacked",
        readonly=True, copy=False,
        help="How many CFDI of the package already became documents.",
    )

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_verify_request(self):
        """Verify request status of ``self``."""
        self.ensure_one()
        self._verify_request()

    def action_download_package(self):
        """Download package of a ready request."""
        self.ensure_one()
        self._download_package()

    def action_unpack_package(self):
        """Unpack a batch of documents from a package zip."""
        self.ensure_one()
        self._unpack_package_batch()

    def action_retry_request(self):
        self.ensure_one()
        request = self._send_and_create_new_request({
            'company_id': self.company_id.id,
            'request_type': self.request_type,
            'receipt_type': self.receipt_type,
            'emission_date_from': self.emission_date_from,
            'emission_date_to': self.emission_date_to,
            'cfdi_uuid': self.cfdi_uuid,
        })

        if not request:
            return False

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_mx_edi.cfdi.request',
            'res_id': request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('l10n_mx_edi.action_l10n_mx_edi_document')
        action['domain'] = [('id', 'in', self.l10n_mx_edi_document_ids.ids)]
        return action

    # -------------------------------------------------------------------------
    # CRON
    # -------------------------------------------------------------------------

    @api.model
    def _cron_verify_requests(self, batch_size=20):
        self._cron_process_requests('in_process_at_sat', batch_size)

    @api.model
    def _cron_download_packages(self, batch_size=20):
        self._cron_process_requests('in_download', batch_size)

    @api.model
    def _cron_process_requests(self, state, batch_size):
        """Run the SAT step the requests waiting in ``state`` need, least recently attempted first.

        :param state: the state whose requests this cron handles.
        :param batch_size: how many requests to handle before committing.
        """
        IrCron = self.env['ir.cron']
        retry_time = fields.Datetime.now() - timedelta(minutes=STATE_RETRY_DELAY[state])
        request_domain = (
            Domain('is_retryable', '=', True)
            & Domain('state', '=', state)
            & (
                Domain('last_cron_attempt', '=', False)
                | Domain('last_cron_attempt', '<=', retry_time)
            )
        )
        IrCron._commit_progress(remaining=self.search_count(request_domain))

        batch = self.search(
            request_domain, order='last_cron_attempt ASC NULLS FIRST, id', limit=batch_size,
        )
        for cfdi_request in batch:
            locked_request = cfdi_request.try_lock_for_update().filtered_domain(request_domain)
            if locked_request and not locked_request._block_if_stale():
                locked_request.last_cron_attempt = fields.Datetime.now()
                try:
                    if locked_request.state == 'in_process_at_sat':
                        locked_request._verify_request(check_is_retryable=False)
                    elif locked_request.state == 'in_download':
                        locked_request._download_package(check_is_retryable=False)
                except UserError as err:
                    # A controlled error occured while processing this request. Since it may
                    # be fixed on its own (e.g. problem from SAT side) or by user action
                    # (e.g. wrong/expired credentials).
                    locked_request.message = str(err)
                except Exception as err:  # noqa: BLE001
                    IrCron._rollback_progress()
                    _logger.exception(
                        "Failed to process CFDI request %s of company %s.",
                        cfdi_request.request_uuid, cfdi_request.company_id.display_name,
                    )
                    cfdi_request.write({
                        'is_retryable': False,
                        'message': _("Something unexpected occurred when processing request: \n%s", err),
                    })
            if not IrCron._commit_progress(1):
                break

    @api.model
    def _cron_unpack_packages(self, batch_size=20):
        IrCron = self.env['ir.cron']
        request_domain = Domain('is_retryable', '=', True) & Domain('state', '=', 'unpacking')
        IrCron._commit_progress(remaining=self.search_count(request_domain))

        for cfdi_request in self.search(request_domain, order='id', limit=batch_size):
            locked_request = cfdi_request.try_lock_for_update().filtered_domain(request_domain)
            if locked_request and not locked_request._block_if_stale():
                try:
                    while locked_request.state == 'unpacking' and IrCron._commit_progress():
                        locked_request._unpack_package_batch(check_is_retryable=False)
                except Exception as err:  # noqa: BLE001
                    IrCron._rollback_progress()
                    _logger.exception(
                        "Failed to unpack package %s of company %s.",
                        cfdi_request.package_uuid, cfdi_request.company_id.display_name,
                    )
                    cfdi_request.write({
                        'is_retryable': False,
                        'message': _("Something unexpected occurred when unpacking package content: \n%s", err),
                    })
            if not IrCron._commit_progress(1):
                break

    # -------------------------------------------------------------------------
    # CFDI Requests Logic
    # -------------------------------------------------------------------------

    @api.model
    def _send_and_create_new_request(self, vals):
        """Send a new package request to the SAT service and create it if successful.

        :param vals: A dictionary with the values to create the request.
        :return: The request record.
        """
        company = self.env['res.company'].browse(vals['company_id'])
        if vals['request_type'] == 'folio':
            if not vals.get('cfdi_uuid'):
                raise UserError(_('Missing Fiscal Folio for this request.'))
            request_type, kwargs = 'folio', {'cfdi_uuid': vals['cfdi_uuid']}
        else:
            date_from = fields.Date.to_date(vals.get('emission_date_from'))
            date_to = fields.Date.to_date(vals.get('emission_date_to'))
            if not date_from or not date_to:
                raise UserError(_('You need to specify a date range for your request.'))
            if date_to < date_from:
                raise UserError(_('Invalid date range for this request.'))

            tz = company.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone()
            if date_to >= datetime.now(tz).date():
                raise UserError(_("The end date must be before today. Today's CFDIs might not be settled yet."))
            if lock_dates := company._get_lock_date_violations(date_from):
                raise UserError(_(
                    'You cannot create a CFDI request prior or inclusive of %s',
                    company._format_lock_dates(lock_dates),
                ))

            request_type = 'issued' if vals['request_type'] == 'batch_issued' else 'received'
            kwargs = {
                'receipt_type': vals['receipt_type'],
                'date_from': date_from,
                'date_to': date_to,
            }

        Client = self.env['l10n_mx_edi.sat.download.client']
        certificate, token = company.sudo()._l10n_mx_edi_get_sat_credentials()
        result = Client._request_download(certificate, token, request_type=request_type, **kwargs)

        code_status = result['code_status']
        if code_status == SAT_SUCCESS_STATUS_CODE:
            return self.create({
                **vals,
                'state': 'in_process_at_sat',
                'request_uuid': result['request_uuid'],
                'message': result['message'],
            })

        request = self.create({**vals, 'state': 'in_process_at_sat'})
        request._apply_sat_error(code_status, result['message'])
        return request

    def _block_if_stale(self):
        """Give up on a request SAT can no longer answer for. Only the cron gives up: the buttons stay
        free to push the record afterwards.

        :return: whether the request was blocked.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        if self.state == 'in_process_at_sat' and now - self.create_date > timedelta(days=SAT_MAX_PROCESS_WAIT_DAYS):
            message = _("This request has been in process for too long. "
                "Retry it manually to resolve it or create a new request.")
        elif self.state == 'in_download' and now - self.ready_at > timedelta(days=SAT_MAX_DOWNLOAD_WAIT_DAYS):
            message = _("This package was not downloaded in time and has expired at SAT. "
                "Create a new request for the same period.")
        elif self.state == 'unpacking' and (
            now - self.attachment_id.create_date > timedelta(days=SAT_MAX_UNPACK_WAIT_DAYS)
        ):
            message = _("The contents of this package couldn't or failed to be extracted after some time. "
                "Retry it manually to resolve it, or download the ZIP to inspect it.")
        else:
            return False

        return self.write({'is_retryable': False, 'message': message})

    def _verify_request(self, check_is_retryable=True):
        self.ensure_one()
        Client = self.env['l10n_mx_edi.sat.download.client']
        certificate, token = self.company_id.sudo()._l10n_mx_edi_get_sat_credentials()
        self._apply_verification(Client._verify_status(certificate, token, self.request_uuid))
        if check_is_retryable and self.state in ('in_process_at_sat', 'in_download'):
            self.is_retryable = True

    def _download_package(self, check_is_retryable=True):
        self.ensure_one()
        Client = self.env['l10n_mx_edi.sat.download.client']
        certificate, token = self.company_id.sudo()._l10n_mx_edi_get_sat_credentials()
        self._apply_package(Client._download_package(certificate, token, self.package_uuid))
        if check_is_retryable and self.state == 'unpacking':
            self.is_retryable = True

    def _apply_verification(self, result):
        self.ensure_one()

        request_status = result['request_status']
        request_message = result['message']

        if request_status in ('1', '2'):  # accepted / in process
            self.message = _(
                'Request is still in process. Try later. \n%(message)s',
                message=request_message
            )
        elif request_status == '4':  # SAT-side error
            self.message = _(
                'SAT processing error, this will be retried. \n%(message)s',
                message=request_message,
            )
        elif request_status == '5':
            # Process rejection here instead of calling `_apply_sat_error`.
            # We know it is a rejection.
            self.write({
                'message': _('Request rejected. \n%(message)s', message=request_message),
                'state': 'rejected',
                'is_retryable': False,
            })
        elif request_status == '6':
            self.write({
                'message': _('Request expired. \n%(message)s', message=request_message),
                'state': 'expired',
                'is_retryable': False,
            })
        elif request_status == '3':  # completed
            package_uuids = result['package_uuids']
            if not package_uuids:
                self.write({
                    'message': _('No documents found with request criteria.'),
                    'state': 'done',
                })
            else:
                values = {
                    'message': _('Package is ready for download.'),
                    'state': 'in_download',
                    'package_uuid': package_uuids[0],
                    'ready_at': fields.Datetime.now(),
                    'last_cron_attempt': False,
                }
                self.write(values)
                # An original request can be split across several packages at SAT. If so,
                # clone request per extra package uuid.
                if len(package_uuids) > 1:
                    package_values = self.copy_data({
                        **values,
                        'request_uuid': self.request_uuid,
                    })[0]
                    self.create([
                        {**package_values, 'package_uuid': uuid, 'ready_at': values['ready_at']}
                        for uuid in package_uuids[1:]
                    ])
        else:
            self.message = _(
                'Unhandled status %(request_status)s. \n%(message)s',
                request_status=request_status or _('No Status'), message=request_message,
            )

    def _apply_package(self, result):
        self.ensure_one()

        code_status = result['code_status']
        message = result['message']
        package_content = result['package_content']

        if code_status != SAT_SUCCESS_STATUS_CODE:
            self._apply_sat_error(code_status, message)
            return

        if not package_content or not zipfile.is_zipfile(io.BytesIO(package_content)):
            self.write({
                'is_retryable': False,
                'message': _("SAT reported the package as sent but it did not arrive."),
            })
            return

        attachment = self.env['ir.attachment'].create({
            'res_model': self._name,
            'res_id': self.id,
            'res_field': 'attachment_id',
            'name': f'{self.package_uuid}.zip',
            'raw': package_content,
            'mimetype': 'application/zip',
        })
        self.write({
            'message': _("Package downloaded successfully. Unpacking documents."),
            'state': 'unpacking',
            'attachment_id': attachment.id,
            'unpacked_count': 0,
        })

    def _unpack_package_batch(self, batch_size=UNPACK_BATCH_SIZE, check_is_retryable=True):
        self.ensure_one()
        with zipfile.ZipFile(io.BytesIO(self.attachment_id.raw.content)) as package:
            docs = package.infolist()
            docs_batch = docs[self.unpacked_count:self.unpacked_count + batch_size]
            docs_to_create = []
            for doc in docs_batch:
                if doc.is_dir() or not doc.filename.lower().endswith('.xml'):
                    _logger.warning("Skipped document creation. %s is not a valid XML document.", doc.filename)
                    continue
                if doc.file_size > DOC_MAX_FILE_SIZE:
                    _logger.warning("Document %s is too big to be imported.", doc.filename)
                    continue

                docs_to_create.append(doc)

            self.env['l10n_mx_edi.document']._create_documents_from_cfdi_files(
                [package.read(doc) for doc in docs_to_create], self
            )
            # Count from the batch to avoid unpacking the package again if docs skipped
            unpacked_count = self.unpacked_count + len(docs_batch)
            is_complete = unpacked_count >= len(docs)

        values = {'unpacked_count': unpacked_count}
        if is_complete:
            # We don't need it anymore so we can delete it.
            self.attachment_id.unlink()
            values.update({
                'message': _("Package attachment downloaded successfully"),
                'state': 'done',
            })
        else:
            values.update({
                'message': _("Unpacked %(done)s of %(total)s documents.", done=unpacked_count, total=len(docs)),
                **({'is_retryable': True} if check_is_retryable else {})
            })
        self.write(values)

    def _apply_sat_error(self, code_error, context_message):
        self.ensure_one()
        if code_error in SAT_EXPIRED_CODES:
            vals = {'state': 'expired'}
        else:
            vals = {'state': 'rejected'}

        message = _(
            'Request was %(state)s with code %(code_status)s: %(message)s',
            state=vals['state'], code_status=code_error or _('No Code'), message=context_message,
        )
        self.write({**vals, 'message': message, 'is_retryable': False})
