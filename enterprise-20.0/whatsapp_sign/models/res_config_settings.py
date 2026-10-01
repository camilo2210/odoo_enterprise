# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sign_whatsapp_enabled = fields.Boolean(
        related='company_id.sign_whatsapp_enabled',
        readonly=False,
    )

    sign_send_request_wa_template_id = fields.Many2one(
        related='company_id.sign_send_request_wa_template_id',
        readonly=False,
        help="Approved WhatsApp template used to send signature requests."
    )

    request_completion_wa_template_id = fields.Many2one(
        related='company_id.request_completion_wa_template_id',
        readonly=False,
        help="Approved WhatsApp template sent when a signature request is completed."
    )

    request_refusal_wa_template_id = fields.Many2one(
        related='company_id.request_refusal_wa_template_id',
        readonly=False,
        help="Approved WhatsApp template sent when a signature request is refused."
    )
