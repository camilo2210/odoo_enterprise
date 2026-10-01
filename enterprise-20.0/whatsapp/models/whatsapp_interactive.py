import re
import itertools

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.addons.whatsapp.tools.text_formatting import format_wa_markup_to_html
from odoo.exceptions import ValidationError
from odoo.tools import format_list, plaintext2html


class WhatsAppInteractive(models.Model):
    _name = 'whatsapp.interactive'
    _inherit = ['whatsapp.base.template']
    _description = 'WhatsApp Interactive Template'
    _order = 'sequence, id'

    sequence = fields.Integer(required=True, default=0)
    header_type = fields.Selection(compute='_compute_header_type', store=True, readonly=False, precompute=True)
    interactive_type = fields.Selection([
        ('list', 'List of detailed options'),
        ('button', 'List of replies'),
        ('cta_url', 'Call-to-action button')], string='Interactive Type', default='list', required=True, tracking=True,
        help="List of detailed options - Allow you to present WhatsApp users with a list of options to choose from\n"
             "List of replies -  Allow you to send up to three predefined replies for users to choose from.\n"
             "Call-to-action button - Allow you to map any URL to a button so you don't have to include the raw URL in the message body.")
    list_button_label = fields.Char(string='Button Label')
    button_ids = fields.One2many(
        comodel_name='whatsapp.interactive.button', inverse_name='wa_interactive_id',
        compute='_compute_button_ids', readonly=False, store=True,
        string='Buttons', copy=True)  # copy buttons to avoid validation error

    # =====================================================
    #                 Constraint Methods
    # =====================================================

    @api.constrains('button_ids', 'interactive_type')
    def _check_buttons(self):
        for tmpl in self:
            button_count = len(tmpl.button_ids)

            allowed_types = {
                'button': {'quick_reply'},
                'cta_url': {'url'},
                'list': {'section', 'question'},
            }[tmpl.interactive_type]

            if set(tmpl.button_ids.mapped('button_type')) - allowed_types:
                raise ValidationError(_(
                    "Button types for a '%(interactive_type)s' interactive template must be one of: %(allowed_types)s.",
                    interactive_type=tmpl.interactive_type,
                    allowed_types=format_list(self.env, sorted(allowed_types), 'or'),
                ))

            # Check that at least one button is present
            if not button_count:
                raise ValidationError(_('An interactive template must have at least one button.'))

            # Validations for CTA URL
            if tmpl.interactive_type == 'cta_url' and button_count != 1:
                raise ValidationError(_("A 'CTA URL' message type should only have one button."))

            # Validations for Interactive Reply Buttons
            if tmpl.interactive_type == 'button':
                if button_count > 3:
                    raise ValidationError(_("An 'Interactive Reply Buttons' message type must have between 1 and 3 buttons."))
                # Check that each button has a unique name
                btn_names = tmpl.button_ids.mapped('name')
                if len({name.strip().lower() for name in btn_names}) != button_count:
                    raise ValidationError(_('Each button must have a unique name.'))

            # Validations for Interactive List
            if tmpl.interactive_type == 'list':
                button_types = tmpl.button_ids.mapped('button_type')

                if button_types.count('section') > 10:
                    raise ValidationError(_('Maximum 10 sections are allowed.'))

                if button_types.count('question') > 10:
                    raise ValidationError(_('Maximum 10 questions are allowed.'))

                # If sections are present, the first item must be a section
                if button_types[0] == 'question' and 'section' in button_types:
                    raise ValidationError(_('If there are sections, the first item must be a section.'))

                # The last item in the list must be a question, not a section
                if button_types[-1] == 'section':
                    raise ValidationError(_('The last list item must be a question.'))

                # No two consecutive sections are allowed
                for button_type_1, button_type_2 in itertools.pairwise(button_types):
                    if button_type_1 == 'section' and button_type_2 == 'section':
                        raise ValidationError(_('Each section must be followed by at least one question.'))

    @api.constrains('header_text', 'header_type')
    def _check_header_text(self):
        super()._check_header_text()
        markdown_patterns = re.compile(r'(\*.*?\*|_.*?_|\~.*?\~|```.*?```)')
        for tmpl in self.filtered(lambda tmpl: tmpl.header_type == 'text'):
            if markdown_patterns.search(tmpl.header_text):
                raise ValidationError(_('Markdown is not allowed inside Header Text.'))

    @api.constrains('body', 'footer_text', 'list_button_label')
    def _check_text_field_lengths(self):
        for tmpl in self:
            if tmpl.body and len(tmpl.body) > 4096:
                raise ValidationError(_('Body cannot exceed 4096 characters.'))
            if tmpl.footer_text and len(tmpl.footer_text) > 60:
                raise ValidationError(_('Footer Text cannot exceed 60 characters.'))
            if tmpl.list_button_label and len(tmpl.list_button_label) > 20:
                raise ValidationError(_('List Button Text cannot exceed 20 characters.'))

    # =====================================================
    #                 Compute Methods
    # =====================================================

    @api.depends('interactive_type')
    def _compute_button_ids(self):
        for tmpl in self:
            tmpl.button_ids = [(5, 0, 0)]

    @api.depends('interactive_type')
    def _compute_header_type(self):
        for tmpl in self:
            # 'none' is the fallback on create, where nothing is set yet
            header_type = tmpl.header_type or 'none'
            # meta only accepts a text header on list and call-to-action templates
            if tmpl.interactive_type in ('list', 'cta_url') and header_type != 'text':
                header_type = 'none'
            tmpl.header_type = header_type

    # ========================================================================
    #         Send Interactive WhatsApp Message
    # ========================================================================

    def _prepare_send_values_header(self, attachment, wa_account_id):
        """Prepare header component for sending WhatsApp interactive template"""
        self.ensure_one()
        header_vals = {}

        if self.header_type == 'text':
            header_vals = {
                'type': 'text',
                'text': self.header_text,
            }
        elif self.header_type in ['image', 'video', 'document'] and attachment:
            header_vals = self.env['whatsapp.message']._prepare_attachment_vals(attachment, wa_account_id)
        return header_vals

    def _prepare_send_values_action_button(self):
        """Prepare Reply Buttons action component for sending WhatsApp interactive template"""
        self.ensure_one()
        return {
            'buttons': [
                {
                    'type': 'reply',
                    'reply': {
                        'id': str(button.id),
                        'title': button.name,
                    },
                } for button in self.button_ids
            ],
        }

    def _prepare_send_values_action_url(self):
        """Prepare CTA URL action component for sending WhatsApp interactive template"""
        self.ensure_one()
        return {
            'name': self.interactive_type,
            'parameters': {
                'display_text': self.button_ids[0].name,
                'url': self.button_ids[0].website_url,
            },
        }

    def _prepare_send_values_action_list(self):
        """Prepare List action component for sending WhatsApp interactive template"""
        self.ensure_one()
        action = {
            'sections': [],
            'button': self.list_button_label,
        }

        current_section = None
        for list_item in self.button_ids:
            if list_item.button_type == 'section':
                # Append the current section to main section if exists
                if current_section:
                    action['sections'].append(current_section)
                # Start a new section
                current_section = {
                    'title': list_item.name,
                    'rows': [],
                }
            elif list_item.button_type == 'question':
                # Initialize current section if not initialized yet
                if not current_section:
                    current_section = {
                        'rows': []
                    }
                row = {
                    'id': str(list_item.id),
                    'title': list_item.name,
                }
                if list_item.description:
                    row['description'] = list_item.description
                current_section['rows'].append(row)

        # Append the last section
        if current_section:
            action['sections'].append(current_section)
        return action

    def _prepare_send_values(self, attachment, wa_account_id):
        """Prepare JSON dictionary for sending WhatsApp interactive template
        through Whatsapp API.

        Note: If an attachment is provided, upload it to Whatsapp and include its ID in `vals`.
        """
        self.ensure_one()
        vals = {
            'type': self.interactive_type,
            'body': {
                'text': self.body,
            },
        }

        # Generate header and footer
        header_vals = self._prepare_send_values_header(attachment, wa_account_id)
        if header_vals:
            vals['header'] = header_vals
        if self.footer_text:
            vals['footer'] = {
                'text': self.footer_text
            }

        # Generate interactive action
        vals['action'] = {
            'button': self._prepare_send_values_action_button,
            'cta_url': self._prepare_send_values_action_url,
            'list': self._prepare_send_values_action_list,
        }[self.interactive_type]()
        return vals

    def _get_formatted_body(self):
        """Get formatted body and header.

        :rtype: Markup
        """
        self.ensure_one()

        body = format_wa_markup_to_html(self.body)
        if self.header_type != 'text':
            return body

        header = plaintext2html(self.header_text, with_paragraph=False)
        return Markup("<p><b>") + header + Markup("</b></p>") + body

    def _get_formatted_footer(self):
        """Get formatted footer.

        :rtype: Markup
        """
        self.ensure_one()
        return format_wa_markup_to_html(self.footer_text)

    def _get_preview_values(self):
        """Get values for previewing the interactive template.

        :rtype: dict
        """
        self.ensure_one()
        return {
            'body': self._get_formatted_body(),
            'buttons': self.button_ids if self.interactive_type != 'list' else None,
            'interactive_list_btn_label': self.list_button_label if self.interactive_type == 'list' else None,
            'header_type': self.header_type,
            'footer_text': self._get_formatted_footer(),
            'language_direction': 'ltr',
        }
