from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WhatsAppInteractiveButton(models.Model):
    _name = 'whatsapp.interactive.button'
    _inherit = ['whatsapp.base.template.button']
    _description = 'WhatsApp Interactive Button'

    wa_interactive_id = fields.Many2one(comodel_name='whatsapp.interactive', required=True, ondelete='cascade', index=True)
    interactive_type = fields.Selection(related='wa_interactive_id.interactive_type')
    button_type = fields.Selection(selection_add=[
        ('question', 'Question'),
        ('section', 'Section')], ondelete={'question': 'set default', 'section': 'set default'})
    description = fields.Char(string='Description')  # For message type Interactive List

    @api.constrains('description', 'name', 'website_url')
    def _check_text_field_lengths(self):
        for button in self:
            # Check 'description' field
            if button.description and len(button.description) > 72:
                raise ValidationError(_('Description cannot exceed 72 characters.'))

            # Check 'name' field
            max_length = 24 if button.interactive_type == 'list' else 20
            if button.name and len(button.name) > max_length:
                raise ValidationError(_('Button Label cannot exceed %(max_length)s characters.', max_length=max_length))

            # Check 'website_url' field
            if button.website_url and len(button.website_url) > 2000:
                raise ValidationError(_('Website Link cannot exceed 2000 characters.'))
