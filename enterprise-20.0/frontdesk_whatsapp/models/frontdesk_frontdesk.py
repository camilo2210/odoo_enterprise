# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FrontdeskFrontdesk(models.Model):
    _inherit = 'frontdesk.frontdesk'

    notify_whatsapp = fields.Boolean('Notify by WhatsApp', groups='frontdesk.frontdesk_group_user')
    whatsapp_template_id = fields.Many2one(
        'whatsapp.template',
        string='WhatsApp Template',
        domain="[('model', '=', 'frontdesk.visitor')]",
        default=lambda self: self.env.ref('frontdesk_whatsapp.frontdesk_whatsapp_template', raise_if_not_found=False),
        ondelete='restrict',
    )

    @api.constrains('host_ids', 'notify_whatsapp')
    def _check_valid_hosts_whatsapp(self):
        for frontdesk in self:
            if frontdesk.notify_whatsapp:
                invalid_hosts = frontdesk.host_ids.filtered(
                    lambda h: not h.work_phone or not h._whatsapp_phone_format(number=h.work_phone)
                )
                if invalid_hosts:
                    raise ValidationError(self.env._(
                        "%(host_names)s must have a valid work phone with a country code to receive visitor arrival notifications via WhatsApp.",
                        host_names=", ".join(invalid_hosts.mapped('name')),
                    ))
