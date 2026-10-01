# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import binascii
import contextlib
from datetime import datetime
from itertools import chain
from xml.etree import ElementTree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    # once we parsed the XML to know if a PDF is embedded inside,
    # we store that information so we don't need to parse it again
    has_embedded_pdf = fields.Boolean('Has Embedded PDF', compute='_compute_has_embedded_pdf', store=True)
    account_setting_ids = fields.One2many('documents.account.folder.setting', 'folder_id')

    @api.depends('has_embedded_pdf')
    def _compute_thumbnail(self):
        """Compute the thumbnail and thumbnail status.

        If the XML invoices contain an embedded PDF, the thumbnail / thumbnail_status
        must have the same behavior as a standard PDF.
        """
        xml_documents = self.filtered(lambda doc: doc.has_embedded_pdf)
        xml_documents.thumbnail = False
        xml_documents.thumbnail_status = 'client_generated'
        super(DocumentsDocument, self - xml_documents)._compute_thumbnail()

    @api.depends('checksum')
    def _compute_has_embedded_pdf(self):
        for document in self:
            document.has_embedded_pdf = bool(document._extract_pdf_from_xml())

    @api.depends_context('uid')
    @api.depends('account_setting_ids')
    def _compute_is_protected(self):
        is_manager = self.env.user.has_group('documents.group_documents_manager')
        user_company_and_false = self.env.user.company_ids.ids + [False]
        protected = self.filtered(
            lambda d: d.account_setting_ids and (not is_manager or d.company_id.id not in user_company_and_false))
        protected.is_protected = True
        super(DocumentsDocument, self - protected)._compute_is_protected()

    @api.model
    def _search_is_protected(self, operator, operand):
        domain = super()._search_is_protected(operator, operand)
        if domain is NotImplemented:
            return NotImplemented
        # Only handle "in" operator and "[True]" operand (see super)
        domain_sync_folders = Domain(
            [('id', 'in', self.env['documents.account.folder.setting'].sudo()._search([]).select(SQL('folder_id')))])
        if self.env.user.has_group('documents.group_documents_manager'):
            return domain | (
                    domain_sync_folders & Domain('company_id', 'not in', self.env.user.company_ids.ids + [False]))
        return domain | domain_sync_folders

    @api.depends('account_setting_ids')
    def _compute_is_company_allowed(self):
        """Overridden to display account folders when a child company is selected."""
        super()._compute_is_company_allowed()
        for document in self.filtered('account_setting_ids'):
            document.is_company_allowed |= document.company_id in self.env.companies.parent_ids

    def _search_is_company_allowed(self, operator, operand):
        domain = super()._search_is_company_allowed(operator, operand)
        if domain is NotImplemented or operator != 'in':
            return NotImplemented
        return domain | (
                Domain('id', 'in', self.env['documents.account.folder.setting'].sudo()._search([]).select(SQL('folder_id')))
                & Domain('company_id', 'parent_of', self.env.companies.ids)
        )

    def _get_child_document_default_company(self):
        """Returns active company if linked to an account setting and active company is child of the setting company."""
        company = super()._get_child_document_default_company()  # Always called to check pre-condition
        if (setting_company_sudo := self.sudo().account_setting_ids.company_id) and self.is_company_allowed and (
                setting_company_sudo in self.env.company.parent_ids):
            return self.env.company
        return company

    def _extract_pdf_from_xml(self):
        """Parse the XML file and return the PDF content if one is found.

        For some invoice files (in the XML format), we can have a PDF embedded inside
        in base 64. We want to be able to preview it in documents.

        We support the UBL format
        > https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice
        """
        self.ensure_one()

        if not self.mimetype or not self.raw:
            return False

        if not (self.mimetype.endswith('/xml')
                or (self.mimetype == 'text/plain' and self.name.lower().endswith('.xml'))):
            return False

        try:
            xml_file_content = self.raw.content.decode()
        except UnicodeDecodeError:
            return False

        # quick filters, to not parse the XML most of the cases
        if "EmbeddedDocumentBinaryObject" not in xml_file_content and "Attachment" not in xml_file_content:
            return False

        try:
            tree = ElementTree.fromstring(xml_file_content)
        except ElementTree.ParseError:
            return False

        attachment_nodes = tree.iterfind('.//{*}EmbeddedDocumentBinaryObject')
        attachment_nodes = chain(attachment_nodes, tree.iterfind('.//{*}Attachment'))

        for attachment_node in attachment_nodes:
            if len(attachment_node):  # the node has children
                continue

            with contextlib.suppress(TypeError, binascii.Error):
                # check file header in case many file are embedded in the XML
                if (pdf_attachment_content := base64.b64decode(attachment_node.text + "====")).startswith(b'%PDF-'):
                    return pdf_attachment_content

        return False

    def account_create_account_move(self, move_type, journal_id=None, partner_id=None):
        if any(document.type == 'folder' for document in self):
            raise UserError(_('You can not create a journal entry from a folder.'))

        if journal_id is None:
            company_journals = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(self.env.company),
            ])
            if move_type == 'statement':
                journal_id = company_journals.filtered(lambda journal: journal.type == 'bank')[:1]
            else:
                journal_id = self.env['account.move']._get_suitable_journal_ids(move_type)[:1]
        elif isinstance(journal_id, int):
            journal_id = self.env['account.journal'].browse(journal_id)

        move = None
        invoices = self.env['account.move']

        # 'entry' are outside of document loop because the actions
        #  returned could be differents (cfr. l10n_be_soda)
        if move_type == 'entry':
            return journal_id.create_document_from_attachment(attachment_ids=self.attachment_id.ids)

        for document in self:
            partner = partner_id or document.partner_id
            if document.res_model == 'account.move' and document.res_id:
                move = self.env['account.move'].browse(document.res_id)
            else:
                creation_context = {'default_move_type': move_type}
                if move_type in ('in_invoice', 'in_refund') and partner and 'property_purchase_currency_id' in partner:
                    supplier_currency = partner.with_company(document.company_id).property_purchase_currency_id
                    if supplier_currency:
                        creation_context['default_currency_id'] = supplier_currency.id
                move = journal_id\
                    .with_context(**creation_context)\
                    ._create_document_from_attachment(attachment_ids=document.attachment_id.id)
            if partner:
                move.partner_id = partner
            if move.statement_line_id:
                move['suspense_statement_line_id'] = move.statement_line_id.id

            invoices |= move

        # When running an action on several documents, this method is called in a
        # loop (because of the "multi" server action). When it is the case, we try
        # to redirect to a list of all created invoices instead of just the last
        # one, using the context.
        action_name_ref = {
            'in_invoice': self.env._("Vendor Bills"),
            'in_refund': self.env._("Vendor Refunds"),
            'in_receipt': self.env._("Vendor Receipts"),
            'out_invoice': self.env._("Customer Invoices"),
            'out_refund': self.env._("Customer Credit Notes"),
        }
        context = dict(self.env.context, default_move_type=move_type)
        documents_active_ids = context.get('documents_active_ids')
        if context.get('active_model') != 'documents.document' or not documents_active_ids:
            invoice_ids = invoices.ids
        else:
            invoice_ids = self.browse(documents_active_ids).mapped('res_id')
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'name': action_name_ref[move_type],
            'view_id': False,
            'view_mode': 'list',
            'views': [(False, "list"), (False, "form")],
            'domain': [('id', 'in', invoice_ids)],
            'context': context,
        }
        if len(invoice_ids) == 1:
            record = move or invoices[0]
            view_id = record.get_formview_id() if record else False
            action.update({
                'view_mode': 'form',
                'views': [(view_id, "form")],
                'res_id': invoice_ids[0],
                'view_id': view_id,
            })
        return action

    def account_create_account_bank_statement(self, journal_id=None):
        # It is not possible to link the doc
        # to the newly created entry as they can be more than one. But importing
        # many times the same bank statement is later checked.
        default_journal = journal_id or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', '=', 'bank'),
        ], limit=1)

        if not default_journal:
            error_msg = self.env['account.journal']._build_no_journal_error_msg(self.env.company.display_name, ['bank'])
            raise UserError(error_msg)

        return default_journal.create_document_from_attachment(attachment_ids=self.attachment_id.ids)

    @api.model
    def _get_base_server_actions_domain(self):
        """ Adds a check on company to avoid using/running actions when not in the right company."""
        domain = super()._get_base_server_actions_domain()
        if self.env.context.get('documents_gc_actions'):
            return domain
        return Domain.AND([
            domain,
            Domain.OR([
                [('state', '!=', 'documents_account_record_create')],
                [('documents_account_journal_id', '=', False)],
                [('documents_account_journal_id.company_id', '=', self.env.company.id)],
            ])
        ])

    @api.model
    def _ensure_account_documents_exist(self):
        self._load_records([
            {
                "xml_id": "documents.document_finance_folder",
                "noupdate": True,
                "values": {
                    "active": True,
                    "type": "folder",
                    "access_internal": "edit",
                    "name": _("Finance"),
                    "sequence": 10,
                }
            }
        ])
        self._load_records([
            {
                "xml_id": "documents.document_finance_taxes_folder",
                "noupdate": True,
                "values": {
                    "active": True,
                    "type": "folder",
                    "access_internal": "edit",
                    "folder_id": self.env.ref("documents.document_finance_folder").id,
                    "name": _("Taxes"),
                    "sequence": 120,
                }
            }
        ])
        self._load_records([
            {
                "xml_id": "documents.document_finance_annual_closing_folder",
                "noupdate": True,
                "values": {
                    "active": True,
                    "type": "folder",
                    "access_internal": "edit",
                    "folder_id": self.env.ref("documents.document_finance_folder").id,
                    "name": _("Annual Closing"),
                    "sequence": 130,
                }
            },
        ])
        self._load_records([
            {
                "xml_id": "documents.document_finance_annual_closing_year_current_folder",
                "noupdate": True,
                "values": {
                    "active": True,
                    "type": "folder",
                    "access_internal": "edit",
                    "folder_id": self.env.ref('documents.document_finance_annual_closing_folder').id,
                    "name": str(datetime.now().year),
                    "sequence": 200,
                }
            },
        ])

    def _get_gc_clear_bin_domain(self):
        query_folder_id = self.env['documents.account.folder.setting']._search(
            [('folder_id', '!=', False)]
        ).select(SQL('folder_id'))
        return Domain.AND([
            super()._get_gc_clear_bin_domain(),
            [('id', 'not in', SQL("(%s)", query_folder_id))],
        ])
