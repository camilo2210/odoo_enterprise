import base64
import json
import logging
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import _get_nilvera_client

_logger = logging.getLogger(__name__)

NILVERA_RESPONSE_STATUS_CODES = {
    'unknown': 'unknown',
    'waitingForApproval': 'waiting',
    'acceptAll': 'accepted',
    'rejectAll': 'rejected',
    'documentAnswered': 'accepted',
    'documentAnsweredAutomatically': 'accepted_automatically',
}
# Once the answer reaches one of these, the signed documents are available.
NILVERA_RESPONSE_SETTLED_STATUSES = {'accepted', 'accepted_automatically', 'rejected'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_tr_nilvera_response_status = fields.Selection(
        string="Nilvera Response Status",
        selection=[
            ('not_sent', "Not sent"),
            ('sent', "Response Sent"),
            ('unknown', "Response Unknown"),
            ('waiting', "Response Waiting"),
            ('error', "Response Error"),
            ('accepted', "Response Accepted"),
            ('accepted_automatically', "Response Accepted Automatically"),
            ('rejected', "Response Rejected"),
        ],
        default='not_sent',
        readonly=True,
        copy=False,
    )
    l10n_tr_nilvera_response_json_file = fields.Binary(
        string="Nilvera Response JSON File",
        copy=False,
        attachment=True,
    )
    l10n_tr_nilvera_response_json_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="Response Payload",
        store=True,
        compute=lambda self: self._compute_linked_attachment_id('l10n_tr_nilvera_response_json_id', 'l10n_tr_nilvera_response_json_file'),
        depends=['l10n_tr_nilvera_response_json_file'],
    )
    l10n_tr_nilvera_response_xml_file = fields.Binary(
        string="Nilvera Response XML File",
        copy=False,
        attachment=True,
    )
    l10n_tr_nilvera_response_xml_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="Response XML",
        store=True,
        compute=lambda self: self._compute_linked_attachment_id('l10n_tr_nilvera_response_xml_id', 'l10n_tr_nilvera_response_xml_file'),
        depends=['l10n_tr_nilvera_response_xml_file'],
    )
    l10n_tr_nilvera_response_pdf_file = fields.Binary(
        string="Nilvera Response PDF File",
        copy=False,
        attachment=True,
    )
    l10n_tr_nilvera_response_pdf_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="Response PDF",
        store=True,
        compute=lambda self: self._compute_linked_attachment_id('l10n_tr_nilvera_response_pdf_id', 'l10n_tr_nilvera_response_pdf_file'),
        depends=['l10n_tr_nilvera_response_pdf_file'],
    )
    l10n_tr_nilvera_response_serial = fields.Char(
        string="e-Response Number",
        copy=False,
        readonly=True,
    )
    l10n_tr_nilvera_response_ready = fields.Boolean(compute='_compute_l10n_tr_nilvera_response_ready')

    @api.depends(
        'country_code', 'picking_type_code', 'l10n_tr_nilvera_uuid',
        'l10n_tr_nilvera_edispatch_xml_id', 'l10n_tr_nilvera_response_status',
        'check_ids.quality_state', 'check_ids.test_type')
    def _compute_l10n_tr_nilvera_response_ready(self):
        for picking in self:
            unit_count_checks = picking.check_ids.filtered(lambda check: check.test_type == 'unit_count')
            picking.l10n_tr_nilvera_response_ready = (
                picking.country_code == 'TR'
                and picking.picking_type_code == 'incoming'
                and picking.l10n_tr_nilvera_uuid
                and picking.l10n_tr_nilvera_edispatch_xml_id
                and picking.l10n_tr_nilvera_response_status in ('not_sent', 'unknown', 'error')
                and unit_count_checks
                and all(check.quality_state in ('pass', 'fail') for check in unit_count_checks)
            )

    def _l10n_tr_get_response_check(self):
        """Return the Unit Count check the answer is built from: a dispatch is answered once, so the last count made wins."""
        self.ensure_one()
        return self.check_ids.filtered(lambda check: check.test_type == 'unit_count')[-1:]

    def _l10n_tr_get_response_serial_number(self):
        """Return the GİB document number for the response: 3-letter serie, 4-digit year, 9-digit sequence — 'QCP2026000000002'."""
        self.ensure_one()
        if not self.l10n_tr_nilvera_response_serial:
            unit_count_check = self._l10n_tr_get_response_check()
            serie = (self.env['ir.sequence'].search([('code', '=', 'quality.point')], limit=1).prefix or '').upper()
            if not serie:
                raise UserError(self.env._(
                    "GİB numbers a dispatch response with a 3-letter serie, taken from the Quality Control Point sequence. Set a 3-letter prefix on that sequence before sending the response."
                ))
            if len(serie) != 3 or not serie.isalpha():
                raise UserError(self.env._(
                    "GİB numbers a dispatch response with a 3-letter serie, taken from the Quality Control Point sequence. Its prefix is %(prefix)s, which cannot be used.",
                    prefix=serie,
                ))
            number = ''.join(filter(str.isdigit, unit_count_check.name or '')) or str(unit_count_check.id or self.id)
            year = fields.Datetime.context_timestamp(self.with_context(tz='Europe/Istanbul'), self.scheduled_date).year
            self.l10n_tr_nilvera_response_serial = f"{serie}{year}{number.zfill(9)}"
        return self.l10n_tr_nilvera_response_serial

    def _l10n_tr_get_dispatch_response_values(self):
        self.ensure_one()
        check = self._l10n_tr_get_response_check()
        lines = check.l10n_tr_response_line_ids
        delivery_datetime = fields.Datetime.context_timestamp(
            self.with_context(tz='Europe/Istanbul'), fields.Datetime.now(),
        ).strftime('%Y-%m-%dT%H:%M:%S')
        values = {
            'DespatchUUID': self.l10n_tr_nilvera_uuid,
            'Serie': self._l10n_tr_get_response_serial_number(),
            'DeliveryDateTime': delivery_datetime,
            'Notes': [line.rejection_reason for line in lines if line.rejection_reason],
        }
        if check._l10n_tr_is_full_acceptance():
            values['AcceptAll'] = True
        else:
            values['DespatchAnswerLines'] = check._l10n_tr_get_response_payload()
        return values

    def action_l10n_tr_send_dispatch_response(self):
        self.ensure_one()
        if not self.l10n_tr_nilvera_response_ready:
            raise UserError(self.env._("Pass or fail the Unit Count quality check on this receipt before sending the response."))
        self._l10n_tr_nilvera_submit_dispatch_response()

    def _l10n_tr_nilvera_submit_dispatch_response(self, post_series=True):
        """Send the answer to Nilvera.

        :param post_series: register the serie with Nilvera and retry once if it
                            is unknown there. False on the retry, to bound the loop.
        """
        self.ensure_one()
        values = self._l10n_tr_get_dispatch_response_values()
        with _get_nilvera_client(self.env._, self.company_id) as client:
            response = client.request(
                "POST",
                endpoint='/edespatch/Purchase/SendAnswer',
                json=values,
                handle_response=False,
            )
            error_message, error_codes = self._l10n_tr_nilvera_get_errors_from_response(client, response)
            if 3009 in error_codes and post_series:
                self._l10n_tr_nilvera_post_response_series(client, values['Serie'])
                return self._l10n_tr_nilvera_submit_dispatch_response(post_series=False)

        if response.status_code == 409:
            # The answer already reached GİB; re-sending would be the wrong recovery.
            self.l10n_tr_nilvera_response_status = 'sent'
            self.message_post(body=self.env._("A response for this dispatch had already been submitted to Nilvera."))
            return
        if response.status_code in {401, 403}:
            raise UserError(self.env._("Oops, seems like you're unauthorised to do this. Try another API key with more rights or contact Nilvera."))
        if response.status_code == 500:
            raise UserError(self.env._("Server error from Nilvera, please try again later."))
        if error_message:
            raise UserError(error_message)
        if response.status_code != 200:
            raise UserError(self.env._("Nilvera refused the dispatch response (HTTP %(status)s).", status=response.status_code))

        self.l10n_tr_nilvera_response_status = 'sent'
        self._l10n_tr_attach_response_payload(values)
        self.message_post(body=self.env._("The dispatch response has been successfully sent to Nilvera."))

    def _l10n_tr_prepare_response_attachment_vals(self, file_type, raw):
        self.ensure_one()
        return {
            'name': f"{self.name}_e_Dispatch_Response.{file_type}",
            'raw': raw,
            'res_model': 'stock.picking',
            'res_id': self.id,
            'res_field': f'l10n_tr_nilvera_response_{file_type}_file',
            'type': 'binary',
            'mimetype': f'application/{file_type}',
        }

    def _l10n_tr_attach_response_payload(self, values):
        self.ensure_one()
        self.l10n_tr_nilvera_response_json_id.unlink()
        raw = json.dumps(values, indent=2, ensure_ascii=False).encode()
        self.env['ir.attachment'].create(self._l10n_tr_prepare_response_attachment_vals('json', raw))
        self.invalidate_recordset(['l10n_tr_nilvera_response_json_id', 'l10n_tr_nilvera_response_json_file'])
        self._compute_linked_attachment_id('l10n_tr_nilvera_response_json_id', 'l10n_tr_nilvera_response_json_file')

    def _l10n_tr_nilvera_get_errors_from_response(self, client, response):
        try:
            payload = response.json()
        except ValueError:
            return '', []
        if isinstance(payload, dict):
            return client._get_error_message_with_codes_from_response(response)
        if response.status_code != 200 and isinstance(payload, str):
            return payload, []
        return '', []

    def _l10n_tr_nilvera_post_response_series(self, client, serie):
        client.request(
            "POST",
            endpoint="/edespatch/AnswerSeries",
            json={'Name': serie[:3].upper(), 'IsActive': True, 'IsDefault': False},
        )

    def _l10n_tr_nilvera_response_channel(self):
        self.ensure_one()
        return 'Sale' if self.picking_type_code == 'outgoing' else 'Purchase'

    def _l10n_tr_nilvera_sync_response_status(self, client, raise_on_failure=False):
        """Read the answer status for this picking and pull its documents once settled.

        :param raise_on_failure: show the user why the status call failed instead
                                 of recording it. True when they asked for the
                                 refresh themselves and are there to read it.
        """
        self.ensure_one()
        channel = self._l10n_tr_nilvera_response_channel()
        try:
            response = client.request(
                "GET",
                endpoint=f"/edespatch/{channel}/{quote(self.l10n_tr_nilvera_uuid)}/Status",
            )
        except UserError as error:
            if raise_on_failure:
                raise
            _logger.warning("Nilvera refused the answer status call for picking %s: %s", self.name, error)
            return self._l10n_tr_nilvera_record_status_failure()

        answer = response.get('Answer')
        if not answer:
            self.l10n_tr_nilvera_response_status = 'waiting'
            return

        status = NILVERA_RESPONSE_STATUS_CODES.get(answer.get('AnswerCode'))
        if not status:
            _logger.warning("Unhandled Nilvera answer status %r for picking %s", answer.get('AnswerCode'), self.name)
            return self._l10n_tr_nilvera_record_status_failure()

        self.l10n_tr_nilvera_response_status = status
        if status in NILVERA_RESPONSE_SETTLED_STATUSES:
            self._l10n_tr_nilvera_fetch_response_documents(client)

    def _l10n_tr_nilvera_record_status_failure(self):
        if self.l10n_tr_nilvera_response_status != 'error':
            self.message_post(body=self.env._("The dispatch response status couldn't be retrieved from Nilvera."))
        self.l10n_tr_nilvera_response_status = 'error'

    def action_l10n_tr_nilvera_get_response_status(self):
        answered = self.filtered(
            lambda picking: picking.l10n_tr_nilvera_uuid
            and (picking.picking_type_code == 'incoming' or picking.l10n_tr_nilvera_send_status == 'succeed')
        )
        for company, pickings in answered.grouped('company_id').items():
            with _get_nilvera_client(self.env._, company) as client:
                for picking in pickings:
                    picking._l10n_tr_nilvera_sync_response_status(client, raise_on_failure=True)

    def _l10n_tr_nilvera_fetch_response_documents(self, client):
        self.ensure_one()
        channel = self._l10n_tr_nilvera_response_channel()
        endpoint = f"/edespatch/{channel}/Answer/{quote(self.l10n_tr_nilvera_uuid)}"
        attachment_vals = []
        if self.picking_type_code == 'incoming' and not self.l10n_tr_nilvera_response_xml_id and (
            xml_response := self._l10n_tr_nilvera_request_response_document(client, f"{endpoint}/xml")
        ):
            attachment_vals.append(self._l10n_tr_prepare_response_attachment_vals('xml', xml_response.encode('utf-8')))
        if not self.l10n_tr_nilvera_response_pdf_id and (
            pdf_response := self._l10n_tr_nilvera_request_response_document(client, f"{endpoint}/pdf")
        ):
            attachment_vals.append(self._l10n_tr_prepare_response_attachment_vals('pdf', base64.b64decode(pdf_response)))
        if not attachment_vals:
            return

        attachments = self.env['ir.attachment'].create(attachment_vals)
        self.invalidate_recordset([
            'l10n_tr_nilvera_response_xml_id', 'l10n_tr_nilvera_response_xml_file',
            'l10n_tr_nilvera_response_pdf_id', 'l10n_tr_nilvera_response_pdf_file',
        ])
        self._compute_linked_attachment_id('l10n_tr_nilvera_response_xml_id', 'l10n_tr_nilvera_response_xml_file')
        self._compute_linked_attachment_id('l10n_tr_nilvera_response_pdf_id', 'l10n_tr_nilvera_response_pdf_file')
        self.message_post(
            body=self.env._("The dispatch response documents have been received from Nilvera."),
            attachment_ids=attachments.ids,
        )

    def _l10n_tr_nilvera_request_response_document(self, client, endpoint):
        try:
            return client.request("GET", endpoint=endpoint)
        except UserError:
            _logger.warning("Nilvera has no document yet at %s for picking %s", endpoint, self.name)
            return None

    def _get_mail_thread_data_attachments(self):
        # EXTENDS 'l10n_tr_nilvera_edispatch'
        return (
            super()._get_mail_thread_data_attachments()
            + self.l10n_tr_nilvera_response_json_id
            + self.l10n_tr_nilvera_response_xml_id
            + self.l10n_tr_nilvera_response_pdf_id
        )

    def _l10n_tr_nilvera_purchase_response_domain(self):
        # Still awaiting an answer, or settled but without the signed PDF filed yet.
        return (
            Domain('picking_type_code', '=', 'incoming')
            & Domain('l10n_tr_nilvera_uuid', '!=', False)
            & (
                Domain('l10n_tr_nilvera_response_status', 'in', ('sent', 'waiting', 'unknown', 'error'))
                | (
                    Domain('l10n_tr_nilvera_response_status', 'in', tuple(NILVERA_RESPONSE_SETTLED_STATUSES))
                    & Domain('l10n_tr_nilvera_response_pdf_file', '=', False)
                )
            )
        )

    def _l10n_tr_nilvera_sale_response_domain(self):
        return (
            Domain('picking_type_code', '=', 'outgoing')
            & Domain('l10n_tr_nilvera_uuid', '!=', False)
            & Domain('l10n_tr_nilvera_send_status', '=', 'succeed')
            & (
                Domain('l10n_tr_nilvera_response_status', 'not in', tuple(NILVERA_RESPONSE_SETTLED_STATUSES))
                | Domain('l10n_tr_nilvera_response_pdf_file', '=', False)
            )
        )

    def _cron_l10n_tr_nilvera_get_response_status(self, batch_size=100):
        self._l10n_tr_nilvera_sync_response_batch(
            self._l10n_tr_nilvera_purchase_response_domain(), batch_size)

    def _cron_l10n_tr_nilvera_get_sale_response_status(self, batch_size=100):
        self._l10n_tr_nilvera_sync_response_batch(
            self._l10n_tr_nilvera_sale_response_domain(), batch_size)

    def _l10n_tr_nilvera_sync_response_batch(self, domain, batch_size):
        pickings = self.search(domain, limit=batch_size)
        for company, company_pickings in pickings.grouped('company_id').items():
            if company.country_code != 'TR' or not company.l10n_tr_nilvera_api_key:
                continue
            with _get_nilvera_client(self.env._, company) as client:
                for picking in company_pickings:
                    picking._l10n_tr_nilvera_sync_response_status(client)
                    self.env['ir.cron']._commit_progress(processed=1)
