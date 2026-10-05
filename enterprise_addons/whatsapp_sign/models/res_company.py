from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    sign_whatsapp_enabled = fields.Boolean(
        string="Enable WhatsApp For Signature Requests",
    )

    sign_send_request_wa_template_id = fields.Many2one(
        'whatsapp.template',
        string='Signature request template',
        domain=[('model', '=', 'sign.request.item')],
    )

    request_completion_wa_template_id = fields.Many2one(
        'whatsapp.template',
        string='Signature completion template',
        domain=[('model', '=', 'sign.request.item')],
    )

    request_refusal_wa_template_id = fields.Many2one(
        'whatsapp.template',
        string='Signature refusal template',
        domain=[('model', '=', 'sign.request.item')],
    )

    def _check_if_whatsapp_sign_is_enabled(self, check_if_approved=False):
        """
        Checks if all required Sign Request WhatsApp templates are configured for the current company.
        """
        self.ensure_one()

        if not self.sign_whatsapp_enabled:
            return False

        templates = [
            self.sign_send_request_wa_template_id,
            self.request_completion_wa_template_id,
            self.request_refusal_wa_template_id,
        ]

        for template in templates:
            # Check if the template exists and user has read access
            template = template.exists()._filtered_access('read')
            if not template or (check_if_approved and template.status != 'approved'):
                return False

        return True
