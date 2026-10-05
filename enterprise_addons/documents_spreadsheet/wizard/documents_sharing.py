from odoo import _, api, fields, models


class DocumentsSharing(models.TransientModel):
    _inherit = "documents.sharing"

    error_message_spreadsheet = fields.Char(
        string="Error Message", compute="_compute_error_message_spreadsheet")

    @api.depends('document_ids',
                 'invite_partner_ids', 'invite_role',
                 'share_access_ids.role', 'access_internal', 'access_via_link')
    def _compute_error_message_spreadsheet(self):
        for wizard in self:
            wizard.error_message_spreadsheet = False
            sp_frozen_docs = wizard.document_ids.filtered(lambda d: d.handler == 'frozen_spreadsheet')

            error_partners = self.env['res.partner']
            is_inviting = wizard.invite_partner_ids
            edit_access_partner = wizard.share_access_ids.filtered(
                lambda s: s.role.endswith('edit') and not s.is_deleted
            ).partner_id
            has_edit = wizard.invite_role == 'edit' if is_inviting else (
                    wizard.access_internal.endswith('edit') or wizard.access_via_link.endswith('edit')
                    or edit_access_partner)
            if has_edit and sp_frozen_docs:
                wizard.error_message_spreadsheet = _(
                    "Read only spreadsheet(s): %(document_names)s.",
                    document_names=', '.join(sp_frozen_docs.sorted('display_name').mapped('display_name')))
                error_partners = edit_access_partner

            if wizard.error_message_spreadsheet and error_partners:
                wizard.error_message_spreadsheet += ' '
                wizard.error_message_spreadsheet += _('Partner(s): %(partner_names)s.',
                    partner_names=', '.join(error_partners.sorted('display_name').mapped('display_name')))

    def _compute_access_internal_help(self):
        super()._compute_access_internal_help()
        for record in self:
            if all(d.handler in ("spreadsheet", "frozen_spreadsheet") for d in record.document_ids):
                if record.access_internal.endswith('view'):
                    record.access_internal_help = _("Can view the spreadsheet. Cannot make changes.")
                elif record.access_internal.endswith('edit'):
                    record.access_internal_help = _("Can edit the spreadsheet, including structure and content.")

    def _compute_access_via_link_help(self):
        super()._compute_access_via_link_help()
        for record in self:
            is_spreadsheet_only = all(d.handler in ("spreadsheet", "frozen_spreadsheet") for d in record.document_ids)
            if is_spreadsheet_only and record.access_via_link.endswith('view'):
                record.access_via_link_help = _("Can view the spreadsheet. Cannot make changes.")
