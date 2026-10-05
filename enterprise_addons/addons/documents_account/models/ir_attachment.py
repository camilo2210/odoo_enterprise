# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, models, api


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _get_pdf_raw(self):
        self.ensure_one()
        if pdf_raw := super()._get_pdf_raw():
            return pdf_raw

        document = self.document_ids.filtered('has_embedded_pdf')[:1]
        return document._extract_pdf_from_xml() if document else False

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        if self.env.context.get('no_document'):
            return attachments
        for attachment in attachments:
            res_id, res_model = attachment.res_id, attachment.res_model
            if not res_id or not res_model:
                continue
            if res_model == 'account.move':
                move = self.env['account.move'].browse(res_id)
                # In order to avoid creation of extra documents we retrict creation of a document to:
                # - attachments of a misc operation
                # - xml file after it has been successfully registered as move attachment
                if move.move_type == 'entry' or attachment.mimetype in ('application/xml', 'text/xml'):
                    attachment._account_update_or_create_documents(move)
            elif res_model == 'account.bank.statement' and attachment.mimetype and (
                    attachment.mimetype == 'application/pdf' or attachment.mimetype.startswith("image/")):
                bank_statement = self.env['account.bank.statement'].browse(res_id)
                attachment._account_update_or_create_documents(bank_statement)
        return attachments

    def write(self, vals):
        res = super().write(vals)

        if self.env.context.get('no_document'):
            return res

        res_model = vals.get('res_model')
        if not res_model or res_model not in ('account.bank.statement', 'account.move'):
            return res

        if res_model == 'account.bank.statement':
            for attachment in self.filtered(lambda a: not a.res_field and a.res_id and a.mimetype and (
                    a.mimetype == 'application/pdf' or a.mimetype.startswith("image/"))):
                attachment._account_update_or_create_documents(
                    self.env['account.bank.statement'].browse(attachment.res_id))

        elif res_model == 'account.move':
            valid_moves = self.env['account.move'].search([
                ('id', 'in', self.mapped('res_id')),
                ('move_type', '=', 'entry')
            ])
            for attachment in self.filtered(
                lambda a: a.res_id and (a.res_id in valid_moves.ids or a.mimetype in ('application/xml', 'text/xml'))
            ):
                attachment._account_update_or_create_documents(
                    self.env['account.move'].browse(attachment.res_id))

        return res

    def _account_update_or_create_documents(self, record, old_journal=None):
        """Create or update documents for the attachments of self using the settings of the journal record.

        :param record: a singleton recordset of account.move or account.bank.statement
        :param old_journal: optional account.journal record. If provided, tags from this journal's
                            settings will be removed from the document (unless they are also in the new journal).
        """
        self = self.filtered('res_model')  # noqa: PLW0642
        if not self:
            return
        record.ensure_one()
        target_journal_ids = [record.journal_id.id]
        if old_journal:
            target_journal_ids.append(old_journal.id)

        settings = self.env['documents.account.folder.setting'].sudo().search([
            ('journal_id', 'in', target_journal_ids),
            ('company_id', 'parent_of', record.company_id.id)
        ])
        settings_by_journal = {s.journal_id: s for s in settings}

        setting = settings_by_journal.get(record.journal_id)
        if not setting:
            return

        new_journal_tags = setting.tag_ids
        old_journal_tags = settings_by_journal.get(old_journal, settings.browse()).tag_ids

        vals_list_create = []
        Documents_sudo = self.env['documents.document'].sudo()
        doc_sudo_by_attachment = Documents_sudo.with_context(active_test=False).search(
            [('attachment_id', 'in', self.ids)]).grouped('attachment_id')
        for att in self:
            doc_sudo = doc_sudo_by_attachment.get(att, self.env['documents.document'])
            tags = (doc_sudo.tag_ids - old_journal_tags) | new_journal_tags if doc_sudo else new_journal_tags

            partner_id = (record.partner_id.id if 'partner_id' in record else False) or doc_sudo.partner_id.id
            values = {
                'active': True,  # if archived, unarchive it
                'folder_id': setting.folder_id.id,
                'partner_id': partner_id,
                'owner_id': record.create_uid.active and record.create_uid.id,
                'tag_ids': [Command.set(tags.ids)]
            }
            if doc_sudo:
                doc_sudo.write(values)
            else:
                # backward compatibility with documents that may be not
                # registered as attachments yet
                values.update({
                    "attachment_id": att.id,
                    "company_id": record.company_id.id,
                })
                vals_list_create.append(values)
        if vals_list_create:
            Documents_sudo.create(vals_list_create)
