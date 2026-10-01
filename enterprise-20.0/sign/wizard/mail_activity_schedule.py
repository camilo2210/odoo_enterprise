# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.fields import Domain
from odoo.exceptions import UserError


class MailActivitySchedule(models.TransientModel):
    _inherit = "mail.activity.schedule"

    sign_template_id = fields.Many2one('sign.template', string="Sign Template", ondelete='cascade')

    reference_doc = fields.Reference(
        string="Linked to",
        compute="_compute_reference_doc",
        selection='_selection_target_model',
    )

    def _compute_reference_doc(self):
        allowed_models = dict(self._selection_target_model())
        for activity in self:
            applied = activity._get_applied_on_records()
            if applied and not activity.is_batch_mode and applied._name in allowed_models:
                activity.reference_doc = f"{applied._name},{applied.id}"
            else:
                activity.reference_doc = None

    @api.onchange('activity_type_id')
    def _onchange_activity_type_id(self):
        super()._onchange_activity_type_id()
        for record in self:
            record.sign_template_id = record.activity_type_id.default_sign_template_id

    def _selection_target_model(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search(
            [('model', '!=', 'sign.request'), ('is_mail_thread', '=', True)]
        )]

    def action_send_sign_request(self):
        self.ensure_one()
        if self.is_batch_mode:
            raise UserError(_("Scheduling a signature request cannot be done for more than one record at a time."))
        reference_doc = f"{self.reference_doc._name},{self.reference_doc.id}" if self.reference_doc else False
        return self.sign_template_id.with_context(
            sign_directly_without_mail=False,
            show_email=True,
            default_log_request_activity=True,
            default_activity_type_id=self.activity_type_id.id,
            default_model='sign.template',
            default_res_ids=[self.sign_template_id.id],
            default_reference_doc=reference_doc,
        ).open_sign_send_dialog()

    def _get_activity_type_available_base_domain(self):
        domain = super()._get_activity_type_available_base_domain()
        if self._sign_exclude_activity_types():
            domain &= Domain('category', '!=', 'sign_request')

        return domain

    def _sign_exclude_activity_types(self):
        """Return True if 'sign_request' activity types should be excluded for this wizard."""
        self.ensure_one()
        # Exclude if the current user is not in the Sign Users group
        not_sign_user = not self.env.user.has_group('sign.group_sign_user')
        # Exclude 'sign_request' activities for non-sign users or for specific models
        return not_sign_user or self.res_model in ['sign.request', 'discuss.channel']
