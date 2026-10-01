from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    field_service_confirmation_email = fields.Boolean(
        related='company_id.field_service_confirmation_email',
        readonly=False,
        string="Confirmation Email",
    )
    field_service_confirmation_mail_template_id = fields.Many2one(
        related='company_id.field_service_confirmation_mail_template_id',
        string="Field Service Confirmation Email Template",
        domain="[('model', '=', 'planning.slot')]",
        readonly=False,
    )
    rating_shift_request_mail_template_id = fields.Many2one(
        'mail.template',
        string="Field Service Intervention Customer Rating Mail Template",
        config_parameter='planning_field_service.rating_shift_request_mail_template_id',
        domain=[('model', '=', 'planning.slot')],
        default=lambda self: self.env.ref('planning_field_service.rating_shift_request_email_template', raise_if_not_found=False),
        readonly=False,
    )

    def set_values(self):
        super().set_values()
        rating_shift_request_email_template = self.env.ref('planning_field_service.rating_shift_request_email_template', raise_if_not_found=False)
        if rating_shift_request_email_template.active != self.group_field_service_allow_customer_ratings:
            rating_shift_request_email_template.active = self.group_field_service_allow_customer_ratings
