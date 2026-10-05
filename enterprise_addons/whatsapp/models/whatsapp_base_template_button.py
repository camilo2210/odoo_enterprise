from urllib.parse import urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin as url_join


class WhatsappBaseTemplateButton(models.AbstractModel):
    _name = 'whatsapp.base.template.button'
    _description = 'WhatsApp Base Template Button'
    _order = 'sequence, id'

    sequence = fields.Integer()
    name = fields.Char(string='Button Text', copy=True)
    button_type = fields.Selection([
        ('url', 'Visit Website'),
        ('quick_reply', 'Quick Reply')], string='Type', required=True, default='quick_reply')
    website_url = fields.Char(string='Website URL')

    @api.constrains('name')
    def _check_name(self):
        if self.filtered(lambda button: button.name and len(button.name) > 25):
            raise ValidationError(_('Button Text cannot exceed 25 characters.'))

    @api.onchange('website_url')
    def _onchange_website_url(self):
        if self.website_url:
            if self.website_url.startswith('/'):
                if (base_url := self.get_base_url()) and 'localhost' not in base_url:
                    self.website_url = url_join(base_url, self.website_url)
            elif (parsed_url := urlsplit(self.website_url)) and not parsed_url.scheme:
                self.website_url = f'https://{self.website_url}'
