# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
import re
import zipfile

from collections import defaultdict
from datetime import datetime, timedelta
from lxml import etree
from werkzeug.urls import url_encode
from zoneinfo import ZoneInfo

from odoo import api, models, modules, fields, _
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
from odoo.tools import SQL
from odoo.addons.l10n_co_edi import xml_utils
from odoo.addons.l10n_co_edi.models.l10n_co_edi_document import COMMERCIAL_STATE_SELECTION, EVENT_FILE_SEQUENCE_CODE


DESCRIPTION_CREDIT_CODE = [
    ("1", "Devolución parcial de los bienes y/o no aceptación parcial del servicio"),
    ("2", "Anulación de factura electrónica"),
    ("3", "Rebaja total aplicada"),
    ("4", "Ajuste de precio"),
    ("5", "Descuento comercial por pronto pago"),
    ("6", "Descuento comercial por volumen de ventas")
]

DESCRIPTION_DEBIT_CODE = [
    ('1', 'Intereses'),
    ('2', 'Gastos por cobrar'),
    ('3', 'Cambio del valor'),
    ('4', 'Otros'),
]

L10N_CO_EDI_TYPE = {
    'Sales Invoice': '01',
    'Export Invoice': '02',
    'Electronic transmission document - type 03': '03',
    'Electronic Sales Invoice - type 04': '04',
    'Credit Note': '91',
    'Debit Note': '92',
    'Event (Application Response)': '96',
}

L10N_CO_EDI_OPERATION_TYPES = {
    '10': {'value': 'Estandar', 'active': True},
    '09': {'value': 'AIU', 'active': True},
    '11': {'value': 'Mandatos', 'active': True},
    '12': {'value': 'Transporte', 'active': False},
    '13': {'value': 'Cambiario', 'active': False},
    '15': {'value': 'Compra Divisas', 'active': False},
    '16': {'value': 'Venta Divisas', 'active': False},
    '20': {'value': 'Nota Crédito que referencia una factura electrónica', 'active': True},
    '22': {'value': 'Nota Crédito sin referencia a facturas', 'active': True},
    '30': {'value': 'Nota Débito que referencia una factura electrónica', 'active': True},
    '32': {'value': 'Nota Débito sin referencia a facturas', 'active': True},
    '23': {'value': 'Inactivo: Nota Crédito para facturación electrónica V1 (Decreto 2242)', 'active': False},
    '33': {'value': 'Inactivo: Nota Débito para facturación electrónica V1 (Decreto 2242)', 'active': False},
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_co_edi_type = fields.Selection(
        selection=[(code, label) for label, code in L10N_CO_EDI_TYPE.items()],
        compute='_compute_l10n_co_edi_type',
        init_storage='_init_l10n_co_edi_type',
        store=True,
        string='Electronic Invoice Type',
    )
    l10n_co_edi_available_operation_types = fields.Char(compute='_compute_l10n_co_edi_available_operation_types')
    l10n_co_edi_operation_type = fields.Selection(
        selection=[(k, v['value']) for k, v in L10N_CO_EDI_OPERATION_TYPES.items()],
        string="Operation Type (CO)",
        compute='_compute_operation_type',
        init_storage='_init_l10n_co_edi_operation_type',
        store=True,
    )

    l10n_co_edi_cufe_cude_ref = fields.Char(
        string="CUFE/CUDE/CUDS",
        compute='_compute_l10n_co_edi_cufe',
        init_storage=lambda model: None,  # skip initialization (False)
        store=True,
        readonly=True,
        copy=False,
        help='Unique ID received by the government when the invoice is signed. Used by the DIAN to identify the invoice.',
    )
    l10n_co_edi_payment_option_id = fields.Many2one('l10n_co_edi.payment.option', string="Payment Option",
                                                    default=lambda self: self.env.ref('l10n_co_edi.payment_option_1', raise_if_not_found=False))
    l10n_co_edi_is_direct_payment = fields.Boolean("Direct Payment from Colombia", compute="_compute_l10n_co_edi_is_direct_payment")
    l10n_co_edi_description_code_credit = fields.Selection(DESCRIPTION_CREDIT_CODE, string="Concepto Nota de Credito")
    l10n_co_edi_description_code_debit = fields.Selection(DESCRIPTION_DEBIT_CODE, string="Concepto Nota de Débito")
    l10n_co_edi_debit_note = fields.Boolean(related="journal_id.l10n_co_edi_debit_note")
    l10n_co_edi_is_support_document = fields.Boolean('Support Document', related='journal_id.l10n_co_edi_is_support_document')

    l10n_co_edi_show_support_doc_button = fields.Boolean(compute='_compute_l10n_co_edi_show_support_doc_button')
    l10n_co_edi_post_time = fields.Datetime(readonly=True, copy=False)
    l10n_co_edi_document_ids = fields.One2many(
        comodel_name='l10n_co_edi.document',
        inverse_name='move_id',
    )
    l10n_co_edi_state = fields.Selection(
        selection=[
            ('invoice_sending_failed', "Sending Failed"),
            ('invoice_pending', "Pending"),
            ('invoice_rejected', "Rejected"),
            ('invoice_accepted', "Accepted"),
        ],
        compute='_compute_l10n_co_edi_states',
        init_storage=lambda model: None,  # skip initialization (False)
        store=True,
        copy=False,
    )
    l10n_co_edi_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute='_compute_l10n_co_edi_attachment_id',
    )
    l10n_co_edi_identifier_type = fields.Selection(
        selection=[
            ('cufe', 'CUFE'),
            ('cude', 'CUDE'),
            ('cuds', 'CUDS'),
        ],
        compute="_compute_l10n_co_edi_identifier_type",
    )
    l10n_co_edi_is_enabled = fields.Boolean(compute="_compute_l10n_co_edi_is_enabled")
    l10n_co_edi_processed_by_get_event_status_cron = fields.Boolean()
    l10n_co_edi_commercial_state = fields.Selection(
        string="Commercial Status",
        selection=COMMERCIAL_STATE_SELECTION,
        compute='_compute_l10n_co_edi_states',
        init_storage=lambda model: None,  # skip initialization (False)
        copy=False,
        store=True,
    )
    l10n_co_edi_claim_reason = fields.Selection(
        string="Claim Reason",
        selection=[
            ('01', "Document with inconsistencies"),
            ('02', "Undelivered merchandise"),
            ('03', "Merchandise partially delivered"),
            ('04', "Service not provided"),
        ],
        copy=False,
    )
    l10n_co_edi_update_commercial_event_enabled = fields.Boolean(compute='_compute_l10n_co_edi_update_commercial_event_enabled')
    l10n_co_edi_is_unsent_contingency_invoice = fields.Boolean(compute='_compute_l10n_co_edi_is_unsent_contingency_invoice')

    def _init_l10n_co_edi_type(self):
        self.env.cr.execute(SQL("""
            UPDATE account_move AS move
            SET l10n_co_edi_type = CASE
                WHEN move.move_type = 'out_refund' THEN %s
                ELSE %s
            END
            FROM res_company AS company
            JOIN res_country AS country
                ON country.id = company.account_fiscal_country_id
            WHERE company.id = move.company_id
            AND country.code = 'CO'
            AND move.l10n_co_edi_type IS NULL
        """,
            L10N_CO_EDI_TYPE['Credit Note'],
            L10N_CO_EDI_TYPE['Sales Invoice'],
        ))

    def _init_l10n_co_edi_operation_type(self):
        self.env.cr.execute(SQL("""
            UPDATE account_move AS move
            SET l10n_co_edi_operation_type = CASE
                WHEN move.move_type = 'out_refund'
                    THEN CASE
                       WHEN move.reversed_entry_id IS NOT NULL THEN '20'
                       ELSE '22'
                    END
                ELSE '10'
            END
            FROM res_company AS company
            JOIN res_country AS country
                ON country.id = company.account_fiscal_country_id
            WHERE company.id = move.company_id
            AND country.code = 'CO'
            AND move.l10n_co_edi_operation_type IS NULL
        """))

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('move_type', 'l10n_co_edi_debit_note')
    def _compute_l10n_co_edi_type(self):
        CO_moves = self.filtered(lambda move: move.company_id.account_fiscal_country_id.code == 'CO')
        for move in CO_moves:
            if move.move_type == 'out_refund':
                move.l10n_co_edi_type = L10N_CO_EDI_TYPE['Credit Note']
            elif move.l10n_co_edi_debit_note:
                move.l10n_co_edi_type = L10N_CO_EDI_TYPE['Debit Note']
            elif not move.l10n_co_edi_type:
                move.l10n_co_edi_type = L10N_CO_EDI_TYPE['Sales Invoice']

    @api.depends('move_type', 'l10n_co_edi_debit_note')
    def _compute_l10n_co_edi_available_operation_types(self):
        active_operation_types = [k for k, v in L10N_CO_EDI_OPERATION_TYPES.items() if v['active']]

        for move in self:
            move.l10n_co_edi_available_operation_types = ','.join(active_operation_types)

            if move.move_type == 'out_invoice':
                if move.l10n_co_edi_debit_note:
                    move.l10n_co_edi_available_operation_types = '30,32'
                else:
                    move.l10n_co_edi_available_operation_types = '10,09,11'
            elif move.move_type == 'out_refund':
                move.l10n_co_edi_available_operation_types = '20,22'

    @api.depends('move_type', 'reversed_entry_id', 'debit_origin_id', 'l10n_co_edi_debit_note')
    def _compute_operation_type(self):
        CO_moves = self.filtered(lambda move: move.country_code == 'CO')
        for move in CO_moves:
            operation_type = '10'
            if move.move_type == 'out_refund':
                operation_type = '20' if move.reversed_entry_id else '22'
            elif move.l10n_co_edi_debit_note:
                operation_type = '30' if move.debit_origin_id else '32'
            move.l10n_co_edi_operation_type = operation_type

    @api.depends('invoice_date_due', 'date')
    def _compute_l10n_co_edi_is_direct_payment(self):
        for rec in self:
            rec.l10n_co_edi_is_direct_payment = (rec.date == rec.invoice_date_due) and rec.company_id.account_fiscal_country_id.code == 'CO'

    @api.depends(
        'move_type',
        'l10n_co_edi_is_support_document',
        'l10n_co_edi_document_ids.state',
        'l10n_co_edi_document_ids.commercial_state',
    )
    def _compute_l10n_co_edi_cufe(self):
        for move in self:
            if move.move_type in ('in_invoice', 'in_refund') and not move.l10n_co_edi_is_support_document:
                move.l10n_co_edi_cufe_cude_ref = move.l10n_co_edi_cufe_cude_ref
                continue

            move.l10n_co_edi_cufe_cude_ref = move.l10n_co_edi_cufe_cude_ref

            documents = move.l10n_co_edi_document_ids.sorted()
            is_accepted_by_issuer = False
            for document in documents:
                if document.state not in ('invoice_pending', 'invoice_accepted'):
                    continue

                # In case a document has been accepted by the issuer, we report the identifier of the first send document when the
                # commercial state was pending.
                if document.commercial_state == 'accepted_by_issuer':
                    is_accepted_by_issuer = True
                if is_accepted_by_issuer and document.commercial_state == 'pending':
                    move.l10n_co_edi_cufe_cude_ref = document.identifier
                    break

                # Otherwise, report the identifier for the 'invoice_accepted' document.
                if not is_accepted_by_issuer and document.state == 'invoice_accepted':
                    move.l10n_co_edi_cufe_cude_ref = document.identifier
                    break

    @api.depends('l10n_co_edi_document_ids', 'l10n_co_edi_document_ids.state', 'l10n_co_edi_document_ids.commercial_state')
    def _compute_l10n_co_edi_states(self):
        for move in self:
            if accepted_doc := move._l10n_co_edi_get_last_accepted_document():
                move.l10n_co_edi_state = accepted_doc.state
                move.l10n_co_edi_commercial_state = accepted_doc.commercial_state
                continue
            move.l10n_co_edi_commercial_state = False
            doc = move.l10n_co_edi_document_ids.sorted()[:1]
            move.l10n_co_edi_state = doc.state if doc else False

    @api.depends('l10n_co_edi_document_ids', 'l10n_co_edi_document_ids.state')
    def _compute_l10n_co_edi_attachment_id(self):
        for move in self:
            move.l10n_co_edi_attachment_id = False
            documents = move.l10n_co_edi_document_ids.sorted()
            for document in documents:
                if document.state == 'invoice_accepted':
                    move.l10n_co_edi_attachment_id = document.attachment_id
                    break

    @api.depends('journal_id', 'move_type', 'l10n_co_edi_type')
    def _compute_l10n_co_edi_identifier_type(self):
        for move in self:
            if move.journal_id.l10n_co_edi_debit_note or move.move_type == 'out_refund' or move.l10n_co_edi_type == '03':
                move.l10n_co_edi_identifier_type = 'cude'  # Debit Notes, Credit Notes, Electronic transmission document - type 03 (contingency)
            elif move.l10n_co_edi_is_support_document:
                move.l10n_co_edi_identifier_type = 'cuds'  # Support Documents (Vendor Bills)
            else:
                move.l10n_co_edi_identifier_type = 'cufe'  # Invoices

    @api.depends('state', 'move_type', 'l10n_co_edi_state')
    def _compute_l10n_co_edi_show_support_doc_button(self):
        for move in self:
            move.l10n_co_edi_show_support_doc_button = (
                    move.l10n_co_edi_is_enabled
                    and move.l10n_co_edi_state != 'invoice_accepted'
                    and move.move_type in ('in_refund', 'in_invoice')
                    and move.state == 'posted'
                    and move.journal_id.l10n_co_edi_is_support_document
            )

    @api.depends('country_code', 'company_currency_id', 'move_type')
    def _compute_l10n_co_edi_is_enabled(self):
        """ Check whether or not the DIAN is needed on this invoice. """
        for move in self:
            move.l10n_co_edi_is_enabled = (
                    move.country_code == "CO"
                    and move.company_currency_id.name == "COP"
                    and move.is_invoice()
            )

    @api.depends('l10n_co_edi_document_ids.state', 'l10n_co_edi_commercial_state')
    def _compute_l10n_co_edi_update_commercial_event_enabled(self):
        for move in self:
            move.l10n_co_edi_update_commercial_event_enabled = (
                    any(doc.state == 'invoice_accepted' for doc in move.l10n_co_edi_document_ids)
                    and move.l10n_co_edi_commercial_state not in ('claimed', 'accepted', 'accepted_by_issuer')
            )

    @api.depends('l10n_co_edi_state', 'l10n_co_edi_type', 'move_type', 'journal_id')
    def _compute_l10n_co_edi_is_unsent_contingency_invoice(self):
        """ Returns whether contingency invoice has been sent to DIAN or not."""
        for move in self:
            move.l10n_co_edi_is_unsent_contingency_invoice = move.move_type == 'out_invoice' and not move.journal_id.l10n_co_edi_debit_note and move.l10n_co_edi_type == '03' and not move.l10n_co_edi_state

    # -------------------------------------------------------------------------
    # Extends
    # -------------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'l10n_co_edi_commercial_state' in fields_list:
            defaults['l10n_co_edi_commercial_state'] = 'pending'
        return defaults

    def _get_lines_with_wrong_partner(self):
        """EXTENDS 'account'. Keep all mandate partners on product lines and tax lines. Tax lines won't have the
        mandate product_id. We therefore keep all mandate partners, even if they happen to not apply to a mandate
        product line.
        """
        mandate_partners = self.line_ids.filtered('product_id.l10n_co_edi_mandate_contract').mapped('partner_id')
        return super()._get_lines_with_wrong_partner().filtered(
            lambda line: line.partner_id not in mandate_partners
        )

    def _post(self, soft=True):
        # EXTENDS account
        res = super()._post(soft=soft)
        for move in self.filtered('l10n_co_edi_is_enabled'):
            # naive local colombian datetime
            now = fields.Datetime.to_string(datetime.now(tz=ZoneInfo('America/Bogota')))
            move.l10n_co_edi_post_time = now

            if move.is_purchase_document() and not move.l10n_co_edi_is_support_document and not move.l10n_co_edi_document_ids:
                self.env['l10n_co_edi.document']._create_document(
                    xml=b'',
                    move=move,
                    state='invoice_accepted',
                    commercial_state='pending',
                    message_json={'status': ''},
                )
            # Raise error when contingency is selected for other move types that's NOT a customer invoice
            if move.l10n_co_edi_type == '03' and (move.move_type != 'out_invoice' or move.journal_id.l10n_co_edi_debit_note):
                raise ValidationError(_("DIAN only allows the generation of contingency documents for Customer Invoices. Please select the correct Electronic Invoice Type."))
        return res

    @api.depends('l10n_co_edi_state')
    def _compute_show_reset_to_draft_button(self):
        # EXTENDS 'account'
        super()._compute_show_reset_to_draft_button()
        for move in self.filtered(lambda m: m.is_sale_document()):
            # Reset to draft is not possible for invoices validated by DIAN
            if any(d.state in ('invoice_pending', 'invoice_accepted') and d.commercial_state == 'pending' for d in move.l10n_co_edi_document_ids):
                move.show_reset_to_draft_button = False

    def _get_name_invoice_report(self):
        # EXTENDS account
        self.ensure_one()
        if self.env.ref('l10n_co_edi.report_vendor_document', raise_if_not_found=False) and \
                self.l10n_co_edi_is_support_document and \
                self.move_type in ('in_refund', 'in_invoice'):
            return 'l10n_co_edi.report_vendor_document'
        elif (self.l10n_co_edi_state == 'invoice_accepted' and self.l10n_co_edi_attachment_id) or self.l10n_co_edi_is_unsent_contingency_invoice:
            return 'l10n_co_edi.report_invoice_document'
        return super()._get_name_invoice_report()

    @api.model
    def _unwrap_attachment(self, file_data, recurse=True):
        # Colombia uses zip files with arbitrary names, and the filenames are arbitrary too. The only way to determine is by unzipping.
        if self.env.company.account_fiscal_country_id.code == 'CO' and file_data['mimetype'] == 'application/zip':
            xml_size_limit_bytes = 10 * 1024 * 1024

            # Do not alter, enforces security. Only these methods reliably bound memory usage during read(n).
            allowed_compression = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            try:
                with io.BytesIO(file_data['attachment'].raw) as buffer, zipfile.ZipFile(buffer) as zipfile_obj:
                    xml_infos = [
                        info for info in zipfile_obj.infolist()
                        if not info.is_dir() and info.filename.lower().endswith('.xml')
                    ]
                    if (
                            len(xml_infos) == 1
                            and xml_infos[0].compress_type in allowed_compression
                            and xml_infos[0].file_size <= xml_size_limit_bytes
                    ):
                        with zipfile_obj.open(xml_infos[0]) as xml_file:
                            xml_content = xml_file.read(xml_size_limit_bytes + 1)
                        if len(xml_content) <= xml_size_limit_bytes:
                            attachment = self.env['ir.attachment'].create({
                                'name': xml_infos[0].filename,
                                'raw': xml_content,
                            })
                            # mutate the original file_data to remove the .zip and replace it with the .xml
                            file_data.update(self._to_files_data(attachment)[0])
            except zipfile.BadZipFile:
                pass

        return super()._unwrap_attachment(file_data, recurse=recurse)

    def _get_import_file_type(self, file_data):
        """ Identify DIAN UBL files. """
        # EXTENDS 'account'
        if (
            file_data['xml_tree'] is not None
            and etree.QName(file_data['xml_tree']).localname != 'AttachedDocument'
            and (ubl_profile := file_data['xml_tree'].findtext('{*}ProfileID'))
            and ubl_profile.startswith('DIAN 2.1:')
        ):
            return 'account.edi.xml.ubl_dian'

        return super()._get_import_file_type(file_data)

    @api.model
    def _get_mail_template(self):
        # EXTENDS 'account'
        self.ensure_one()
        mail_template = super()._get_mail_template()
        if self.country_code == 'CO':
            xmlid = 'l10n_co_edi.email_template_edi_credit_note' if self.move_type == 'out_refund' else 'l10n_co_edi.email_template_edi_invoice'
            return self.env.ref(xmlid, raise_if_not_found=False) or mail_template
        return mail_template

    def _duplicated_ref_ids_depends(self):
        # EXTENDS 'account'
        return super()._duplicated_ref_ids_depends() + ['l10n_co_edi_cufe_cude_ref']

    def _get_duplicate_ref_sql_conditions(self, moves, move_table_and_alias):
        # EXTENDS 'account'
        to_query = super()._get_duplicate_ref_sql_conditions(moves, move_table_and_alias)

        moves = moves.filtered(lambda m:
                               m.country_code == 'CO'
                               and m.move_type == 'in_invoice'
                               and m.l10n_co_edi_cufe_cude_ref
                               )
        if moves:
            sql_condition = SQL("""
                move.l10n_co_edi_cufe_cude_ref = duplicate_move.l10n_co_edi_cufe_cude_ref
                AND duplicate_move.move_type = 'in_invoice'
            """)
            to_query.append((moves, sql_condition))

        return to_query

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def l10n_co_edi_action_update_event_status(self):
        self.l10n_co_edi_document_ids.filtered(lambda doc: doc.state == 'invoice_rejected').unlink()

        for move in self.try_lock_for_update():
            track_id = move._l10n_co_edi_get_last_accepted_document().identifier
            if not track_id:
                continue

            self.env['l10n_co_edi.document']._send_get_status_event(move, track_id)
            if not modules.module.current_test:
                self.env.cr.commit()

            # unlink duplicate documents and only keep the most recent ones
            # for this process we exclude the original document containing the invoice data
            documents = move.l10n_co_edi_document_ids.sorted()[:-1]
            grouped_documents = documents.grouped(key='commercial_state')
            for commercial_state, duplicate_documents in grouped_documents.items():
                duplicate_documents.sorted()[1:].unlink()

    def l10n_co_edi_send_event_update_status_received(self):
        self._l10n_co_edi_send_event_update_status('received')

    def l10n_co_edi_send_event_update_status_claimed(self):
        self._l10n_co_edi_send_event_update_status('claimed')

    def l10n_co_edi_send_event_update_status_goods_received(self):
        self._l10n_co_edi_send_event_update_status('goods_received')

    def l10n_co_edi_send_event_update_status_accepted(self):
        self._l10n_co_edi_send_event_update_status('accepted')

    def l10n_co_edi_send_event_update_status_accepted_by_issuer(self):
        self._l10n_co_edi_send_event_update_status('accepted_by_issuer')

    def _l10n_co_edi_send_event_update_status(self, commercial_state_next):
        if not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(self.env._("Only invoicing users can update the DIAN commercial status."))

        self.ensure_one()
        self._l10n_co_edi_validate_send_event_update_data()
        document = self.env['l10n_co_edi.document']._send_commercial_event(self, commercial_state_next)

        if document.state == 'invoice_accepted':
            # Send mail
            AccountMoveSend = self.env['account.move.send']
            mail_template = self.env.ref('l10n_co_edi.email_template_commercial_event')
            mail_lang = AccountMoveSend._get_default_mail_lang(self, mail_template)

            self.with_context(
                email_notification_allow_footer=True,
            ).message_post(
                message_type='comment',
                subtype_id=self.env.ref('mail.mt_comment').id,
                body=AccountMoveSend._get_default_mail_body(self, mail_template, mail_lang),
                subject=AccountMoveSend._get_default_mail_subject(self, mail_template, mail_lang),
                partner_ids=self.partner_id.ids,
                attachments=[(self.l10n_co_edi_attachment_id.name, self.l10n_co_edi_attachment_id.raw)],
            )

    def _l10n_co_edi_validate_send_event_update_data(self):
        errors = []
        # Validate required data for vendor bills
        if self.move_type in ('in_invoice', 'in_refund'):
            if not self.ref:
                errors.append(self.env._("The Bill Reference is required to send commercial events."))

            if not self.l10n_co_edi_cufe_cude_ref:
                errors.append(self.env._("The Bill CUFE/CUDE is required to send commercial events."))

        if errors:
            raise ValidationError('\n'.join(errors))

        # Validate required data for invoices and vendor bills
        if self.partner_id and not self.partner_id.vat:
            raise RedirectWarning(
                message=self.env._("The receiving partner's identification number is required to send commercial events."),
                action={
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'context': {'create': False},
                    'view_mode': 'form',
                    'views': [[self.env.ref('base.view_partner_form').id, 'form']],
                    'res_id': self.partner_id.id,
                },
                button_text=self.env._("Go to Partner"),
            )

    def _l10n_co_edi_get_mail_commercial_state_label(self):
        self.ensure_one()
        commercial_states = dict(self._fields['l10n_co_edi_commercial_state']._description_selection(self.with_context(lang=self.partner_id.lang).env))
        return commercial_states.get(self.l10n_co_edi_commercial_state, '')

    def _l10n_co_edi_get_electronic_document_number(self):
        self.ensure_one()
        if not self.l10n_co_edi_attachment_id:
            return None

        if self.move_type in ('in_invoice', 'in_refund') and not self.l10n_co_edi_is_support_document:
            root = etree.fromstring(xml_utils._unzip(self.l10n_co_edi_attachment_id.raw.content))
        else:
            root = etree.fromstring(self.l10n_co_edi_attachment_id.raw.content)

        nsmap = {k: v for k, v in root.nsmap.items() if k}  # empty namespace prefix is not supported for XPaths
        return root.findtext('./cbc:ID', namespaces=nsmap)

    def l10n_co_edi_action_send_bill_support_document(self):
        self.ensure_one()
        xml, errors = self.env['account.edi.xml.ubl_dian']._export_invoice(self)
        if errors:
            raise UserError(self.env._("Error(s) when generating the UBL attachment:\n- %s", '\n- '.join(errors)))
        doc = self._l10n_co_edi_send_invoice_xml(xml)
        if doc.state == 'invoice_rejected':
            if self.env['account.move.send']._can_commit():
                self.env.cr.commit()
            raise UserError(self.env._("Error(s) when sending the document to the DIAN:\n- %s",
                                       "\n- ".join(doc.message_json['errors']) or doc.message_json['status']))

    def _l10n_co_edi_get_invoice_report_qr_code_value(self):
        """ Returns the value to be embedded inside the QR Code on the PDF report.
        For Support Documents, see section 12.2 ('Anexo-Tecnico-Documento-Soporte[...].pdf').
        Otherwise, see section 11.7 ('Anexo-Tecnico-[...]-1-9.pdf').
        """
        self.ensure_one()
        attachment = self.l10n_co_edi_attachment_id
        if self.move_type in ('in_invoice', 'in_refund') and not self.l10n_co_edi_is_support_document:
            xml_bytes = xml_utils._unzip(attachment.raw)
            root = etree.fromstring(etree.fromstring(xml_bytes).findtext('.//{*}Description') or xml_bytes)
        else:
            root = etree.fromstring(attachment.raw.content)

        return xml_utils._get_qr_code_value(root, self.currency_id, self.l10n_co_edi_is_support_document)

    def _l10n_co_edi_get_invoice_report_qr_code_src(self):
        self.ensure_one()
        encoded_params = url_encode({
            'barcode_type': 'QR',
            'quiet': 0,
            'value': self._l10n_co_edi_get_invoice_report_qr_code_value(),
            'width': 180,
            'height': 180,
        })
        return f'/report/barcode/?{encoded_params}'

    def _l10n_co_edi_get_extra_invoice_report_values(self):
        """ Get the values used to render the PDF """
        self.ensure_one()
        document = self._l10n_co_edi_get_last_accepted_document()
        # contingency invoice
        if self.l10n_co_edi_is_unsent_contingency_invoice:
            return {'identifier': _("The CUDE code will be created once the Electronic Document is sent.")}
        if not document:
            return {'identifier': _("The CUDS code will be created once the Electronic Document is sent.")}
        return {
            'signing_datetime': document.datetime.replace(microsecond=0),
            'identifier': document.identifier,
        }

    def _l10n_co_edi_get_invoice_prepayments(self):
        """ Collect the prepayments linked to an account.move (based on the partials)
        :returns: a list of dict of the form: [{'name', 'amount', 'date'}]
        """
        if not self.is_sale_document():
            return []
        lines = self.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        prepayment_by_move = defaultdict(float)
        source_exchange_move = {}
        for field in ('debit', 'credit'):
            for partial in lines[f'matched_{field}_ids'].sorted('exchange_move_id.id'):
                counterpart_line = partial[f'{field}_move_id']
                # Aggregate the exchange difference amount
                if partial.exchange_move_id:
                    source_exchange_move[partial.exchange_move_id] = counterpart_line
                elif counterpart_line.move_id in source_exchange_move:
                    counterpart_line = source_exchange_move[counterpart_line.move_id]
                    if counterpart_line not in prepayment_by_move:
                        continue
                # Exclude the partials created after creating a credit note from an existing move
                if (
                        (counterpart_line.move_id.move_type == 'out_refund' and lines.move_type == 'out_invoice')
                        or (counterpart_line.move_id.move_type == 'out_invoice' and lines.move_type == 'out_refund')
                ):
                    continue
                prepayment_by_move[counterpart_line] += partial.amount
        return [
            {
                'name': line.name,
                'date': line.date,
                'amount': amount,
            }
            for line, amount in prepayment_by_move.items()
        ]

    def _l10n_co_edi_send_invoice_xml(self, xml):
        """ Main method called by the Send & Print wizard / on a Support Document
        It unlinks the previous rejected documents, create a new one, send it to DIAN and logs in the chatter
        if it is accepted.
        """
        self.ensure_one()
        self.l10n_co_edi_document_ids.filtered(lambda doc: doc.state == 'invoice_rejected').unlink()
        document = self.env['l10n_co_edi.document']._send_to_dian(xml=xml, move=self)
        if document.state == 'invoice_accepted':
            self.message_post(
                body=self.env._(
                    "The %s was accepted by the DIAN.",
                    dict(document.move_id._fields['move_type']._description_selection(self.env))[document.move_id.move_type],
                ) if not document.move_id.company_id.l10n_co_edi_demo_mode else self.env._(
                    "The %s was validated locally in Demo Mode.",
                    dict(document.move_id._fields['move_type']._description_selection(self.env))[document.move_id.move_type],
                ),
                attachment_ids=document.attachment_id.copy().ids,
            )
        return document

    def _l10n_co_edi_get_attached_document_filename(self):
        self.ensure_one()
        # remove every non-word char or underscore, keep only the alphanumeric characters
        return re.sub(r'[\W_]', '', self.name)

    def _l10n_co_edi_get_commercial_event_document_filename(self, file_ext):
        self.ensure_one()
        prefix = 'ar' if file_ext == 'xml' else 'z'
        vat = self.company_id.partner_id._get_vat_without_verification_code().zfill(10)
        year = fields.Datetime.now().strftime("%y")

        suffix = self.with_company(self.company_id).env['ir.sequence'].next_by_code(EVENT_FILE_SEQUENCE_CODE)
        if not suffix:
            sequence = self.env['ir.sequence'].sudo().create([{
                'name': f"Commercial Event File Name ({self.company_id.name})",
                'code': EVENT_FILE_SEQUENCE_CODE,
                'company_id': self.company_id.id,
                'implementation': 'no_gap',
                'use_date_range': True,
            }])
            suffix = sequence.next_by_id()

        return f'{prefix}{vat}000{year}{int(suffix):0{8}X}'

    def _l10n_co_edi_get_last_accepted_document(self):
        self.ensure_one()
        return next(
            (d for d in self.l10n_co_edi_document_ids.sorted() if d.state == 'invoice_accepted'),
            self.env['l10n_co_edi.document'],
        )

    def _l10n_co_edi_cron_update_event_status(self, *, limit=3):
        date_limit = fields.Datetime.now().date() - timedelta(days=30)

        # There is no clear-cut way to distinguish processed and non-processed moves
        # so we need an extra field to prevent multiple batches from processing the same record
        to_process_domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('l10n_co_edi_commercial_state', 'in', ('pending', 'received', 'goods_received')),
            ('l10n_co_edi_cufe_cude_ref', '!=', False),
            ('invoice_date', '>=', date_limit),
            ('l10n_co_edi_processed_by_get_event_status_cron', '=', False),
        ]

        records = self.search(domain=to_process_domain, limit=limit)
        records.l10n_co_edi_action_update_event_status()
        records.l10n_co_edi_processed_by_get_event_status_cron = True

        remaining = self.search_count(domain=to_process_domain)
        if not remaining:
            # reset processed by cron field
            processed_records = self.search([('l10n_co_edi_processed_by_get_event_status_cron', '=', True)])
            processed_records.l10n_co_edi_processed_by_get_event_status_cron = False

        self.env['ir.cron']._commit_progress(len(records), remaining=remaining)

    def _l10n_co_edi_get_electronic_invoice_type_info(self):
        if self.move_type == 'out_invoice':
            return 'DIAN 2.1: Nota Débito de Factura Electrónica de Venta' if self.l10n_co_edi_debit_note else 'DIAN 2.1: Factura Electrónica de Venta'
        elif self.move_type == 'in_invoice':
            return 'DIAN 2.1: documento soporte en adquisiciones efectuadas a no obligados a facturar.'
        elif self.move_type == 'in_refund':
            return 'DIAN 2.1: Nota de ajuste al documento soporte en adquisiciones efectuadas a sujetos no obligados a expedir factura o documento equivalente'
        return 'DIAN 2.1: Nota Crédito de Factura Electrónica de Venta'


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _l10n_co_edi_get_product_code(self):
        """
        For identifying products, different standards can be used.  If there is a barcode, we take that one, because
        normally in the GTIN standard it will be the most specific one.  Otherwise, we will check the
        :return: (standard, product_code)
        """
        self.ensure_one()
        if self.product_id:
            if self.move_id.l10n_co_edi_type == L10N_CO_EDI_TYPE['Export Invoice']:
                if not self.product_id.l10n_co_edi_customs_code:
                    raise UserError(_('Exportation invoices require custom code in all the products, please fill in this information before validating the invoice'))
                return (self.product_id.l10n_co_edi_customs_code, '020', 'Partida Alanceraria')
            if (
                    self.move_type == "in_refund" and
                    self.move_id.l10n_co_edi_is_support_document and
                    (code := self.product_id.default_code or self.product_id.barcode or self.product_id.unspsc_code_id.code)
            ):
                return (code, '999', 'Estándar de adopción del contribuyente')
            elif self.product_id.barcode:
                return (self.product_id.barcode, '010', 'GTIN')
            elif self.product_id.unspsc_code_id:
                return (self.product_id.unspsc_code_id.code, '001', 'UNSPSC')
            elif self.product_id.default_code:
                return (self.product_id.default_code, '999', 'Estándar de adopción del contribuyente')

        return ('1010101', '001', '')
