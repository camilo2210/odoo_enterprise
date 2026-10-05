from odoo import api, fields, models, Command
from odoo.exceptions import ValidationError


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    state = fields.Selection(selection_add=[('sign', 'Request Signature')], ondelete={'sign': 'cascade'})
    sign_template_id = fields.Many2one(
        'sign.template', string='Sign Template', ondelete='restrict', compute='_compute_sign_template_id',
        inverse='_inverse_sign_template_id', store=True, domain="[('active', '=', True)]"
    )
    sign_role_ids = fields.Many2many(
        'sign.item.role', string='Sign Roles', compute='_compute_sign_role_ids',
        inverse='_inverse_sign_role_ids', store=False
    )

    @api.constrains('sign_template_id', 'state')
    def _check_sign_template_conflicts(self):
        """ Ensure template roles aren't already linked to a different action. """
        batch_roles = self.env['sign.item.role']
        for action in self:
            if action.state == 'sign' and action.sign_template_id:
                roles = action.sign_template_id.sign_item_ids.responsible_id
                if batch_roles & roles:
                    raise ValidationError(self.env._("You are trying to save multiple actions that share the same role!"))
                batch_roles |= roles

                conflicting_roles = action.sign_template_id.sign_item_ids.responsible_id.filtered(
                    lambda r: r.ir_actions_server_id and r.ir_actions_server_id != action
                )
                if conflicting_roles:
                    raise ValidationError(
                        self.env._(
                            "The sign roles of the template that you are selecting are currently automated in another "
                            "server action. Please select a template with different sign roles or use different sign roles "
                            "in the target template."
                        )
                    )

    @api.depends('state', 'model_id')
    def _compute_sign_template_id(self):
        """ Clear sign_template_id and old roles when state is not 'sign' and clear linked roles when model_id changes. """
        # Reset linked_field_id for roles when model_id changes.
        for action in self:
            if action.state == 'sign' and action.sign_template_id:
                roles = action.sign_role_ids.filtered(lambda r: r.linked_field_id)
                if roles:
                    roles.sudo().write({'linked_field_id': False})

        # Reset the previous roles when the state of the server action changes.
        to_reset = self.filtered(lambda a: a.state != 'sign' and a.sign_template_id)
        if to_reset:
            old_roles = self.env['sign.item.role'].search([('ir_actions_server_id', 'in', to_reset.ids)])
            if old_roles:
                old_roles.sudo().write(self._get_role_reset_values())
            to_reset.sign_template_id = False

    def _inverse_sign_template_id(self):
        """ Handle template changes, cleanup old roles and link new ones. """
        # Batch fetch all roles linked to the current actions.
        all_old_roles = self.env['sign.item.role'].search([('ir_actions_server_id', 'in', self.ids)])
        roles_map = {a_id: self.env['sign.item.role'] for a_id in self.ids}
        for role in all_old_roles:
            roles_map[role.ir_actions_server_id.id] += role

        for action in self:
            # Retrieve pre-fetched roles for this specific action and reset it.
            old_roles = roles_map[action.id]
            if action.sign_template_id:
                new_roles = action.sign_template_id.sign_item_ids.responsible_id
                roles_to_reset = old_roles - new_roles
                if roles_to_reset:
                    roles_to_reset.sudo().write(self._get_role_reset_values())
            else:
                if old_roles:
                    old_roles.sudo().write(self._get_role_reset_values())

    @api.depends('sign_template_id', 'sign_template_id.sign_item_ids', 'sign_template_id.sign_item_ids.responsible_id')
    def _compute_sign_role_ids(self):
        """ Compute the sign item roles for the selected template. """
        for action in self:
            action.sign_role_ids = action.sign_template_id.sign_item_ids.responsible_id if action.sign_template_id else False

    def _inverse_sign_role_ids(self):
        """ Update the role records when sign_role_ids is modified. Called upon widget updates to role configuration. """
        for action in self:
            if action.state == 'sign' and action.sign_template_id:
                # Link all template roles to this action if not already linked.
                roles = action.sign_template_id.sign_item_ids.responsible_id
                roles_to_link = roles.filtered(lambda r: r.ir_actions_server_id != action)
                if roles_to_link:
                    roles_to_link.sudo().write({'ir_actions_server_id': action.id})

    def _name_depends(self):
        """ Returns the list of fields that the action name depends on. """
        return [*super()._name_depends(), "sign_template_id"]

    def _generate_action_name(self):
        """ Generates a descriptive name for the sign request action. """
        self.ensure_one()
        if self.state == 'sign' and self.sign_template_id:
            return self.env._('Request Signature for %(template_name)s', template_name=self.sign_template_id.name)
        return super()._generate_action_name()

    @api.model
    def _get_role_reset_values(self):
        """ Default values to reset a role when it's no longer linked to an action. """
        return {
            'signer_type': 'fixed',
            'ir_actions_server_id': False,
            'sign_action_partner_id': False,
            'linked_field_id': False,
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_sign_actions(self):
        """ Reset roles when action is deleted. """
        roles = self.env['sign.item.role'].search([('ir_actions_server_id', 'in', self.ids)])
        if roles:
            roles.sudo().write(self._get_role_reset_values())

    def _run_action_sign_multi(self, eval_context=None):
        """ Creates and sends signature requests for each record in the evaluation context. """
        if not self.sign_template_id or self._is_recompute() or not (eval_context and 'model' in eval_context):
            return False

        odoobot = self.env.ref('base.user_root')
        for record in eval_context.get('records'):
            request_items = []
            roles = self.sign_template_id.sign_item_ids.responsible_id.sorted(lambda r: (r.sequence, r.id))

            for order, role in enumerate(roles, start=1):
                partner = False

                if role.signer_type == 'fixed':
                    partner = role.sign_action_partner_id or role.assign_to
                    if partner and not partner.email:
                        partner = False
                elif role.signer_type == 'linked_field' and role.linked_field_id:
                    linked = record[role.linked_field_id.name]
                    if linked:
                        if linked._name == 'res.users' and linked.partner_id.email:
                            partner = linked.partner_id
                        elif linked._name == 'res.partner' and linked.email:
                            partner = linked

                if partner:
                    request_items.append(Command.create({
                        'partner_id': partner.id,
                        'role_id': role.id,
                        'mail_sent_order': order,
                    }))

            if request_items and len(request_items) == len(roles):
                sign_req = self.env['sign.request'].with_user(odoobot).create({
                    'subject': self.env._('Signature Request for %(template_name)s', template_name=self.sign_template_id.name),
                    'template_id': self.sign_template_id.id,
                    'reference': self.sign_template_id.name,
                    'request_item_ids': request_items,
                    'reference_doc': '%s,%s' % (record._name, record.id or 0),
                })
                record.with_user(odoobot).message_post(
                    body=self.env._("A signature request has been linked to this document: %s", sign_req._get_html_link()),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return False
