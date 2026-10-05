from odoo import api, models
from odoo.exceptions import UserError


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    def action_archive(self):
        res = super().action_archive()
        self.env['res.company'].sudo().search([]).filtered(
            lambda company: company.field_service_confirmation_mail_template_id in self
        ).write({
            'field_service_confirmation_email': False,
            'field_service_confirmation_mail_template_id': False,
        })
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_customer_ratings_mail_template(self):
        if self.env['ir.config_parameter'].sudo().get_int('planning_field_service.rating_shift_request_mail_template_id') in self.ids:
            raise UserError(self.env._(
                "This email template can’t be deleted because it’s required to collect customer ratings for shifts. "
                "Choose another template or disable the feature in Planning settings.",
            ))

    @api.ondelete(at_uninstall=False)
    def _unlink_field_service_confirmation_mail_template(self):
        self.env['res.company'].sudo().search([]).filtered(
            lambda company: company.field_service_confirmation_mail_template_id in self
        ).field_service_confirmation_email = False
