from odoo import _, fields, models
from odoo.fields import Domain


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    whatsapp_channel_count = fields.Integer(string="# WhatsApp Chats", related='partner_id.wa_channel_count')

    def action_open_lead_wa_channels(self):
        self.ensure_one()
        if not self.partner_id:
            domain = Domain.FALSE
        else:
            domain = Domain.AND([
                Domain('channel_type', '=', 'whatsapp'),
                Domain('channel_partner_ids', 'in', self.partner_id.ids),
            ])
        return {
            'name': _('WhatsApp Chats'),
            'type': 'ir.actions.act_window',
            'res_model': 'discuss.channel',
            'domain': domain,
            'views': [(self.env.ref('whatsapp.discuss_channel_view_list_whatsapp').id, 'list')],
        }
