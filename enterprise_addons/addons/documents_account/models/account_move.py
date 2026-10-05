# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move']

    suspense_statement_line_id = fields.Many2one(
        comodel_name='account.bank.statement.line',
        string="Request document from a bank statement line",
        index='btree_not_null',
    )

    has_documents = fields.Boolean(string='Has Documents', compute='_compute_has_documents')

    @api.depends('attachment_ids')
    def _compute_has_documents(self):
        result = self.env['documents.document']._read_group(
            domain=[('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            groupby=['res_id'],
        )
        has_documents_ids = {r[0] for r in result}
        for move in self:
            move.has_documents = move.id in has_documents_ids

    def write(self, vals):
        main_attachment_id = vals.get('message_main_attachment_id')
        new_documents = [False] * len(self)

        old_journal_per_move = {}
        if 'journal_id' in vals:
            moves_changing_journal = self.filtered(lambda m: m.journal_id.id != vals['journal_id'])
            old_journal_per_move = {m: m.journal_id for m in moves_changing_journal}

        journals_changed = [move in old_journal_per_move for move in self]
        moves_with_updated_partner = self.filtered(
            lambda move: vals.get('partner_id', move.partner_id.id) != move.partner_id.id
        )
        for i, move in enumerate(self):
            if not main_attachment_id or move.env.context.get('no_document') or move.move_type == 'entry':
                continue
            attachments_to_sync = move._get_document_attachments_to_sync()

            if not attachments_to_sync:
                new_documents[i] = True
            elif len(attachments_to_sync) == 1:
                previous_attachment_id = move.message_main_attachment_id.id
                if not previous_attachment_id:
                    new_documents[i] = True
                elif previous_attachment_id != main_attachment_id:
                    if document := move._get_document_for_attachments([previous_attachment_id]).get(previous_attachment_id):
                        # Replacing a single existing attachment
                        document.attachment_id = main_attachment_id
                    else:
                        # If no old document found to update, create a new one
                        new_documents[i] = True
            # Multiple attachments exist
            elif not move._get_document_for_attachments([main_attachment_id]).get(main_attachment_id):
                new_documents[i] = True

        res = super().write(vals)
        for new_document, journal_changed, move in zip(new_documents, journals_changed, self):
            attachments_to_sync = move._get_document_attachments_to_sync()
            if (new_document or journal_changed) and attachments_to_sync:
                old_journal = old_journal_per_move.get(move)
                attachments_to_sync._account_update_or_create_documents(move, old_journal=old_journal)

        for move in moves_with_updated_partner:
            move._sync_partner_on_document()
        return res

    def _get_document_for_attachments(self, attachment_ids):
        if not attachment_ids:
            return {}
        if any(isinstance(item, bool) or not isinstance(item, int) for item in attachment_ids):
            raise ValueError(self.env._("Invalid attachment ids: IDs must be integers."))

        # Search also in previous_attachment_ids to handle the case where
        # the attachment is not the main one due to versioning
        documents = (
            self.env["documents.document"]
            .sudo()
            .search([
                "|",
                ("attachment_id", "in", attachment_ids),
                ("previous_attachment_ids", "in", attachment_ids),
            ])
        )
        # Create a mapping of documents per attachment_id
        documents_by_attachment = dict.fromkeys(attachment_ids, self.env["documents.document"])
        for document in documents:
            if document.attachment_id.id in attachment_ids:
                documents_by_attachment[document.attachment_id.id] = document
            for prev_attachment in document.previous_attachment_ids:
                if prev_attachment.id in attachment_ids:
                    documents_by_attachment[prev_attachment.id] = document
        return documents_by_attachment

    def button_reconcile_with_st_line(self):
        """ When using the "Reconciliation Request" next activity on the statement line's chatter, the invoice is linked
        to this statement line through the 'suspense_statement_line_id' field.
        When checking this link on your invoice, you are able to click on a button triggering this method opening the
        bank reconciliation widget for this specific statement line to easily match it with the current invoice.

        :return: An action opening the bank reconciliation widget.
        """
        self.ensure_one()
        st_line = self.suspense_statement_line_id
        rec_pay_lines = self.line_ids.filtered(lambda x: x.account_id.account_type in ('asset_receivable', 'liability_payable'))
        default_todo_command = ','.join(['add_new_amls'] + [str(x) for x in rec_pay_lines.ids])
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            default_context={
                'search_default_journal_id': st_line.journal_id.id,
                'search_default_statement_id': st_line.statement_id.id,
                'default_journal_id': st_line.journal_id.id,
                'default_st_line_id': st_line.id,
                'default_todo_command': default_todo_command,
            },
        )

    def _sync_partner_on_document(self):
        for move in self:
            if not move.message_main_attachment_id:
                continue
            doc = self.env['documents.document'].sudo().search([('attachment_id', '=', move.message_main_attachment_id.id)], limit=1)
            if not doc or doc.partner_id == move.partner_id:
                continue
            doc.partner_id = move.partner_id

    def action_view_documents_account_move(self):
        self.ensure_one()
        domain = [('res_model', '=', self._name), ('res_id', '=', self.id)]
        documents = self.env['documents.document'].search(domain)
        default_user_folder_id = (
            documents[0].user_folder_id
            if len(set(documents.mapped('user_folder_id'))) == 1
            else False
        )

        return {
            **self.env['ir.actions.actions']._for_xml_id('documents.document_action_preference'),
            'domain': domain,
            'context': {'searchpanel_default_user_folder_id': default_user_folder_id},
        }
