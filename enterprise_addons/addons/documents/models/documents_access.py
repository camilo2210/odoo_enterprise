from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import consteq


class DocumentsAccess(models.Model):
    _name = 'documents.access'
    _description = 'Document / Partner'
    _log_access = False

    document_id = fields.Many2one('documents.document', required=True, bypass_search_access=True, index=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', ondelete='cascade', index=True)
    group_id = fields.Many2one('res.group.functional', ondelete='cascade')
    role = fields.Selection(
        [('view', 'Viewer'), ('edit', 'Editor')],
        string='Role', required=False, index=True)
    last_access_date = fields.Datetime('Last Accessed On', required=False)
    expiration_date = fields.Datetime('Expiration', index=True)

    _unique_document_access_by_partner_or_group = models.UniqueIndex(
        '(document_id, partner_id, group_id) NULLS NOT DISTINCT',
        "This partner/group is already set on this document.",
    )
    _role_or_last_access_date = models.Constraint(
        """CHECK(
            (partner_id IS NOT NULL AND (role IS NOT NULL or last_access_date IS NOT NULL)) OR
            (group_id IS NOT NULL AND role IS NOT NULL AND last_access_date IS NULL))
        """,
        "partner must either have a role or have a set last_access_date, group must have a role",
    )
    _check_partner_or_group = models.Constraint(
        'CHECK((partner_id IS NOT NULL AND group_id IS NULL) OR (partner_id IS NULL AND group_id IS NOT NULL))',
        'Sharing Access must apply to either a partner or a group.',
    )

    @api.constrains("partner_id")
    def _check_partner_id(self):
        """Avoid to have bad data when the access is created from a public user or in a CRON."""
        forbidden_users = (self.env.ref('base.user_root'), self.env.ref('base.public_user'))
        for access in self:
            if access.partner_id.user_ids in forbidden_users:
                raise ValidationError(_('This user can not be member.'))

    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        documents = self.env['documents.document'].browse(
            [vals['document_id'] for vals in vals_list])
        documents.check_access('write')
        return vals_list

    def write(self, vals):
        if 'partner_id' in vals or 'group_id' in vals or 'document_id' in vals:
            raise AccessError(_('Access documents, partners, and groups cannot be changed.'))

        self.document_id.check_access('write')
        return super().write(vals)

    @api.autovacuum
    def _gc_expired(self):
        self.search([('expiration_date', '<=', fields.Datetime.now())], limit=1000).unlink()

    ######################
    # Partner invitation #
    ######################

    def _is_signup_available(self):
        return (
            self.env['res.users'].sudo()._get_signup_invitation_scope() == 'b2c'
            and self.role
            and (not self.expiration_date or self.expiration_date > fields.Datetime.now())
            and not self.partner_id.with_context(active_test=False).user_ids
            and self.partner_id
        )

    def _get_member_signup_token(self):
        """Token used to invite a member to create a user.

        The token is built using the ID of the access, so we can remove
        the member to invalidate the invitation, or use the expiration
        date.
        """
        self.ensure_one()
        return tools.hmac(
            self.env(su=True),
            'documents-member-signup-token',
            (self.id, self.partner_id.id),
        )

    @api.model
    def _get_member_from_token(self, member_id, token):
        member_sudo = self.browse(member_id).sudo().exists()
        return (
            bool(member_sudo)
            and consteq(member_sudo._get_member_signup_token(), token)
            and member_sudo
        )
