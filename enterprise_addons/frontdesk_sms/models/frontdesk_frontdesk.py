# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FrontdeskFrontdesk(models.Model):
    _inherit = 'frontdesk.frontdesk'

    notify_sms = fields.Boolean('Notify by SMS', groups='frontdesk.frontdesk_group_user')
    sms_template_id = fields.Many2one(
        'sms.template',
        string='SMS Template',
        domain="[('model', '=', 'frontdesk.visitor')]",
        default=lambda self: self.env.ref('frontdesk_sms.frontdesk_sms_template', raise_if_not_found=False),
        ondelete='restrict',
    )

    @api.constrains('host_ids', 'notify_sms')
    def _check_valid_hosts_sms(self):
        for frontdesk in self:
            if frontdesk.notify_sms and (invalid_hosts := frontdesk.host_ids.filtered(lambda h: not h.work_phone)):
                raise ValidationError(self.env._(
                    "%(host_names)s must have a valid Phone to be informed about visitor arrival.",
                    host_names=", ".join(invalid_hosts.mapped('name')),
                ))
