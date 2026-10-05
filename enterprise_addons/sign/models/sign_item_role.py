# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.sign.models.sign_request_item import QES_IAP_SERVICE_NAME


class SignItemRole(models.Model):
    _name = 'sign.item.role'
    _description = "Signature Item Role"
    _rec_name = "name"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    default = fields.Boolean(required=True, default=False)
    sequence = fields.Integer(string="Default order", default=10)

    auth_method = fields.Selection(string="Authentication", selection=[
        ('sms', 'Unique Code via SMS')
    ], default=False, help="Force the signatory to identify using a second authentication method")

    change_authorized = fields.Boolean('Change Authorized', help="If checked, recipient of a document with this role can be changed after having sent the request. Useful to replace a signatory who is out of office, etc.")
    assign_to = fields.Many2one(
        'res.partner',
        string='Assign to',
        help="assign the current user or the customer as a signer by default",
    )

    signer_type = fields.Selection([('fixed', 'Fixed Signer'), ('linked_field', 'Linked Field')], string="Signer Type", default='fixed', required=True)
    sign_action_partner_id = fields.Many2one('res.partner', string='Automated Action Partner', copy=False,
        help="Partner used when this role is configured in server actions."
    )
    ir_actions_server_id = fields.Many2one('ir.actions.server', string="Automated Action", copy=False,
        help="Automated action that configures this role when used in server actions."
    )
    linked_field_id = fields.Many2one('ir.model.fields', string="Linked Partner Field", copy=False,
        domain="[('model_id', '=', ir_actions_server_id.model_id), ('relation', 'in', ['res.users', 'res.partner']), ('ttype', '=', 'many2one')]"
    )

    item_ids = fields.One2many('sign.item', 'responsible_id', string="Signature Items")

    auth_credits_remaining = fields.Integer(string="Credits", compute="_compute_remaining_credits")
    requires_external_signature = fields.Boolean(
        string="Requires External Signature", compute='_compute_requires_external_signature',
        help="Whether signers with this role cryptographically sign the document themselves, "
             "using an external service.")

    @api.depends('auth_method')
    def _compute_requires_external_signature(self):
        self.requires_external_signature = False

    def _get_external_signature_provider(self):
        """ Service producing the signatures of signers with this role, named as the
        qualified signature host knows it. """
        self.ensure_one()
        return False

    def _get_external_signature_provider_name(self):
        """ Name of the service producing the signatures of signers with this role, as the signer knows it. """
        self.ensure_one()
        return False

    def _get_external_signature_provider_logo_path(self):
        """ Path to the logo branding the service producing the signatures of signers with this role. """
        self.ensure_one()
        return False

    @api.constrains('signer_type', 'sign_action_partner_id', 'linked_field_id', 'ir_actions_server_id')
    def _check_action_signer_requirements(self):
        for role in self:
            if not role.ir_actions_server_id:
                continue

            if role.signer_type == 'fixed' and not role.sign_action_partner_id:
                raise ValidationError(self.env._("Please specify a Fixed Signer for the role '%s'.", role.name))
            elif role.signer_type == 'linked_field' and not role.linked_field_id:
                raise ValidationError(self.env._("Please specify a Linked Field for the role '%s'.", role.name))

    def _get_iap_service_name(self):
        """IAP service that this role's extra authentication is billed to. Externally produced
        signatures are always billed to the qualified signature service, regardless of the
        provider that produces them."""
        self.ensure_one()
        if self.requires_external_signature:
            return QES_IAP_SERVICE_NAME
        return self._get_auth_method_iap_mapping().get(self.auth_method)

    @api.depends('auth_method')
    def _compute_remaining_credits(self):
        for role in self:
            credits = 0
            iap_service_name = role._get_iap_service_name()
            if iap_service_name:
                credits = self.env['iap.account'].sudo().get_credits(iap_service_name)
            role.auth_credits_remaining = credits

    def action_manage_credits(self):
        for role in self:
            iap_service_name = role._get_iap_service_name()
            if iap_service_name:
                iap_account = self.env['iap.account'].get(iap_service_name)
            return iap_account.action_open_iap_account()

    def write(self, vals):
        vals.pop('default', None)
        if 'auth_method' in vals:
            # a signer externally signing the document is recognized by their role, so changing
            # it under a signature already started will finalize on the wrong one. The
            # reverse is refused too, as strict ordering is only enforced when the request is
            # created, so a live request cannot be changed to require an external signature
            signs_documents = self.new({'auth_method': vals['auth_method']}).requires_external_signature
            roles_to_check = self.filtered(
                lambda role: role.auth_method != vals['auth_method']
                and (signs_documents or role.requires_external_signature))
            if roles_to_check:
                conflicting_item = self.env['sign.request.item'].search([
                    ('role_id', 'in', roles_to_check.ids),
                    ('sign_request_id.state', '=', 'sent'),
                    '|', ('state', '=', 'completed'), ('is_mail_sent', '=', True),
                ], limit=1)
                if conflicting_item:
                    raise UserError(self.env._(
                        "A signature request using the role %s is already in progress, so its authentication "
                        "method cannot be changed.",
                        conflicting_item.role_id.name
                    ))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_role(self):
        for role in self:
            if role.default or role.ir_actions_server_id:
                raise AccessError(_("The role %s is required by the Sign application and cannot be deleted.", role.name))

    @api.model
    def _get_auth_method_iap_mapping(self):
        return {'sms': 'sms'}
