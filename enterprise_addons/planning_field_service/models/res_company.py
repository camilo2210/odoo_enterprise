from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    field_service_confirmation_email = fields.Boolean(default=True)
    field_service_confirmation_mail_template_id = fields.Many2one(
        'mail.template',
        default=lambda self: self.env.ref('planning_field_service.mail_template_data_intervention_details', raise_if_not_found=False),
    )
