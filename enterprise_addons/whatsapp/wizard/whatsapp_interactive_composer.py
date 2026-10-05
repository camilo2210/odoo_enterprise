from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError


class WhatsAppInteractiveComposer(models.TransientModel):
    _name = 'whatsapp.interactive.composer'
    _description = 'Send WhatsApp Interactive Wizard'

    discuss_channel_id = fields.Many2one('discuss.channel', string='Discussion Channel', required=True, ondelete='cascade')
    wa_interactive_id = fields.Many2one(
        comodel_name='whatsapp.interactive', string='Interactive Template', required=True, ondelete='cascade',
        default=lambda self: self._default_wa_interactive_id())
    preview_whatsapp = fields.Html(compute='_compute_preview_whatsapp', string='Message Preview')

    def _raise_no_template_error(self):
        if self.env.user.has_group('whatsapp.group_whatsapp_admin'):
            raise RedirectWarning(
                _('No WhatsApp Interactive Templates are available.'),
                self.env.ref('whatsapp.whatsapp_interactive_action').id,
                _('Configure Templates'),
            )
        else:
            raise ValidationError(_('No WhatsApp Interactive Templates are available.'))

    def _default_wa_interactive_id(self):
        wa_interactive = self.env['whatsapp.interactive'].search([], limit=1)
        if not wa_interactive:
            self._raise_no_template_error()
        return wa_interactive

    @api.depends('wa_interactive_id')
    def _compute_preview_whatsapp(self):
        for record in self:
            wa_interactive = record.wa_interactive_id
            if wa_interactive:
                preview_vals = wa_interactive._get_preview_values()
                record.preview_whatsapp = self.env['ir.qweb']._render('whatsapp.template_message_preview', preview_vals)
            else:
                record.preview_whatsapp = None

    def action_send_whatsapp_interactive(self):
        self.ensure_one()
        self.discuss_channel_id.check_access('read')
        if not self.discuss_channel_id.whatsapp_channel_active:
            raise UserError(_('Conversation closed, replies are only allowed within 24 hours.'))

        header_attachment = self.wa_interactive_id.header_attachment_id
        attachment_ids = header_attachment.copy({
            'res_id': self.discuss_channel_id.id,
            'res_model': self.discuss_channel_id._name,
        }).ids if header_attachment else []
        kwargs = {
            'attachment_ids': attachment_ids,
            'body': self.wa_interactive_id._get_formatted_body(),
            'message_type': 'whatsapp_message',
            'subtype_xmlid': 'mail.mt_comment',
            'wa_interactive_id': self.wa_interactive_id.id,
        }
        self.discuss_channel_id.message_post(**kwargs)
