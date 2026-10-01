from odoo import api, fields, models


class DocumentsShareAccess(models.TransientModel):
    _name = 'documents.sharing.access'
    _description = "Documents share access"

    documents_sharing_id = fields.Many2one('documents.sharing', 'Documents share', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', ondelete='cascade')
    group_id = fields.Many2one('res.group.functional', ondelete='cascade')
    all_partner_ids = fields.Many2many('res.partner', compute='_compute_all_partner_ids')

    # Rights edition
    role = fields.Selection('_get_role_options', string='Role', required=True)
    expiration_date = fields.Datetime('Expiration')
    original_expiration_date = fields.Datetime('Original Expiration')
    is_deleted = fields.Boolean()

    # Additional readonly fields for displaying information
    partner_is_me = fields.Boolean(string="Is me", compute="_compute_partner_is_me")
    user_in_group = fields.Boolean(string="In Group", compute="_compute_user_in_group")

    # Edition flags
    has_user = fields.Boolean(compute='_compute_has_user')
    has_warning_no_access = fields.Boolean(compute="_compute_has_warning_no_access")
    is_on_single_document = fields.Boolean(compute="_compute_is_on_single_document")
    is_readonly = fields.Boolean(related="documents_sharing_id.is_readonly")

    _check_partner_or_group = models.Constraint(
        'CHECK((partner_id IS NOT NULL AND group_id IS NULL) OR (partner_id IS NULL AND group_id IS NOT NULL))',
        'Sharing Access must apply to a partner or to a group (but not both).',
    )

    @api.model
    def _get_role_options(self):
        return self.env['documents.sharing']._get_role_options()

    @api.depends_context('uid')
    @api.depends('partner_id')
    def _compute_partner_is_me(self):
        me = self.env.user.partner_id
        for record in self:
            record.partner_is_me = record.partner_id == me

    @api.depends_context('uid')
    @api.depends('group_id')
    def _compute_user_in_group(self):
        me = self.env.user
        for record in self:
            record.user_in_group = me in record.group_id.user_ids

    @api.depends('documents_sharing_id.document_ids')
    def _compute_is_on_single_document(self):
        for record in self:
            record.is_on_single_document = record.documents_sharing_id.is_single

    @api.depends('partner_id.user_ids')
    def _compute_has_user(self):
        for record in self:
            record.has_user = bool(record.partner_id.user_ids)

    @api.depends('documents_sharing_id.access_via_link', 'documents_sharing_id.invite_partner_ids',
                 'documents_sharing_id.invite_group_ids', 'partner_id.user_ids', 'group_id', 'is_deleted')
    def _compute_has_warning_no_access(self):
        if self.env['res.users'].sudo()._get_signup_invitation_scope() == 'b2c':
            self.has_warning_no_access = False
            return

        for record in self:
            record.has_warning_no_access = (
                    not record.documents_sharing_id.invite_partner_ids
                    and not record.documents_sharing_id.invite_group_ids  # we are modifying rights not inviting
                    and record.documents_sharing_id.access_via_link.endswith('none')
                    and not record.has_user
                    and not record.is_deleted
                    and not record.group_id)

    @api.depends('partner_id', 'group_id.user_ids')
    def _compute_all_partner_ids(self):
        for access in self:
            access.all_partner_ids = access.partner_id + access.group_id.user_ids.partner_id

    def action_resend_invitation(self):
        if self.has_warning_no_access:
            notification_params = {'title': self.env._('Enable access before inviting'), 'type': 'danger'}
        elif self.group_id:
            notification_params = {'title': self.env._('Groups cannot be invited'), 'type': 'warning'}
        else:
            notification_params = self.documents_sharing_id._action_send_invitation(self.partner_id)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': notification_params,
        }
