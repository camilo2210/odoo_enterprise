# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import logging

from ast import literal_eval

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError
from odoo.addons.whatsapp.tools import phone_validation as wa_phone_validation

_logger = logging.getLogger(__name__)


class WhatsappComposer(models.TransientModel):
    _name = 'whatsapp.composer'
    _description = 'Send WhatsApp Wizard'

    def _raise_no_template_error(self, res_model):
        if self.env.user.has_group('whatsapp.group_whatsapp_admin'):
            raise RedirectWarning(
                _("No approved WhatsApp Templates are available for this model."),
                self.env.ref('whatsapp.whatsapp_template_action').id,
                _("Configure Templates"),
                {'search_default_model': res_model}
            )
        else:
            raise ValidationError(_("No approved WhatsApp Templates are available for this model."))

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        context = self.env.context
        if ('wa_template_id' in fields or 'res_model' in fields) and context.get('active_model'):
            result['res_model'] = context['active_model']
            wa_template_id = self.env['whatsapp.template']._find_default_for_model(result['res_model'])
            if wa_template_id and not result.get('wa_template_id'):
                result['wa_template_id'] = wa_template_id.id
            elif not wa_template_id and not result.get('wa_template_id'):
                self._raise_no_template_error(result['res_model'])

        if context.get('active_ids') or context.get('active_id'):
            result['res_ids'] = context.get('active_ids') or [context.get('active_id')]
        if context.get('active_ids') and len(context['active_ids']) > 1:
            result['batch_mode'] = True
        return result

    # documents
    attachment_id = fields.Many2one('ir.attachment', index=True)
    res_ids = fields.Char('Document IDs', required=True)
    res_model = fields.Char('Document Model Name', required=True)
    batch_mode = fields.Boolean("Is Multiple Records")

    # content
    phone = fields.Char(string="Phone", compute="_compute_number", readonly=False, store=True)
    blocklisted_phone_number_count = fields.Integer(compute="_compute_phone_validation_counts")
    invalid_phone_number_count = fields.Integer(compute="_compute_phone_validation_counts")
    wa_template_id = fields.Many2one(comodel_name="whatsapp.template", string="Template")
    preview_whatsapp = fields.Html(compute="_compute_preview_whatsapp", string="Message Preview")

    # free texts
    number_of_free_text = fields.Integer(string="Number of free text", compute='_compute_number_of_free_text')
    number_of_free_text_button = fields.Integer(string="Number of free text Buttons", compute='_compute_number_of_free_text_button')
    is_header_free_text = fields.Boolean(compute='_compute_is_header_free_text')
    is_button_dynamic = fields.Boolean(compute='_compute_is_button_dynamic')
    header_text_1 = fields.Char(string="Header Free Text")
    free_text_1 = fields.Char(string="Free Text 1")
    free_text_2 = fields.Char(string="Free Text 2")
    free_text_3 = fields.Char(string="Free Text 3")
    free_text_4 = fields.Char(string="Free Text 4")
    free_text_5 = fields.Char(string="Free Text 5")
    free_text_6 = fields.Char(string="Free Text 6")
    free_text_7 = fields.Char(string="Free Text 7")
    free_text_8 = fields.Char(string="Free Text 8")
    free_text_9 = fields.Char(string="Free Text 9")
    free_text_10 = fields.Char(string="Free Text 10")
    button_dynamic_url_1 = fields.Char(string="Button Url 1")
    button_dynamic_url_2 = fields.Char(string="Button Url 2")

    # ------------------------------------------------------------
    # COMPUTES
    # ------------------------------------------------------------

    @api.depends('wa_template_id')
    @api.depends_context('default_phone')
    def _compute_number(self):
        """ In single mode, 'phone' is the number to contact (can be set through
        context, for example when forced through UI). In multi mode it is more
        an informational field, holding the first record found numbers. """
        for composer in self:
            records = self.env[composer.res_model].browse(literal_eval(composer.res_ids))
            numbers = []
            use_default_recipient = composer.wa_template_id.use_default_recipient
            recipients_phone_info = (
                records._phone_get_recipients_info() if use_default_recipient else {}
            )
            for record in records[:12]:
                if use_default_recipient:
                    if num := recipients_phone_info[record.id]['number']:
                        numbers.append(num)
                elif composer.wa_template_id.phone_field:
                    try:
                        numbers.append(record._find_value_from_field_path(composer.wa_template_id.phone_field))
                    except UserError as err:
                        error_msg = _("Template %(template_name)s holds a wrong configuration for 'phone field'\n%(error_msg)s",
                                      template_name=composer.wa_template_id.name,
                                      error_msg=err.args[0]
                                     )
                        raise ValidationError(error_msg) from err
            if not composer.batch_mode:
                phone = self.env.context.get('default_phone')
                if not phone:
                    phone = numbers[0] if numbers and numbers[0] else composer.phone
            elif not numbers:
                phone = False
            else:
                other_count = len(records) - len(numbers)
                phone = ', '.join(self._extract_digits(num) for num in numbers if num)
                if other_count:
                    phone += _(", ... (%s Others)", other_count)
            composer.phone = phone

    @api.depends('phone', 'batch_mode')
    def _compute_phone_validation_counts(self):
        for composer in self:
            records = self._get_active_records()
            blocklisted_phone_number_count = 0
            invalid_phone_number_count = 0
            blocklisted_numbers = self.env['whatsapp.blocklist'].sudo().search([
                ('wa_account_id', '=', composer.wa_template_id.wa_account_id.id),
            ]).mapped('number')
            if composer.batch_mode:
                use_default_recipient = composer.wa_template_id.use_default_recipient
                recipients_phone_info = (
                    records._phone_get_recipients_info() if use_default_recipient else {}
                )
                for rec in records:
                    mobile_number = False
                    if use_default_recipient:
                        # Already formatted (E164)
                        mobile_number = recipients_phone_info[rec.id]['sanitized']
                    elif composer.wa_template_id.phone_field:
                        mobile_number = rec._whatsapp_phone_format(fpath=composer.wa_template_id.phone_field)
                    if not mobile_number:
                        invalid_phone_number_count += 1
                    else:
                        formatted_number = wa_phone_validation.wa_phone_format_for_blacklist(mobile_number)
                        if formatted_number in blocklisted_numbers:
                            blocklisted_phone_number_count += 1
            elif composer.phone:
                sanitize_number = records._whatsapp_phone_format(number=composer.phone)
                if not sanitize_number:
                    invalid_phone_number_count = 1
                else:
                    formatted_number = wa_phone_validation.wa_phone_format_for_blacklist(sanitize_number)
                    if formatted_number in blocklisted_numbers:
                        blocklisted_phone_number_count += 1
            else:
                invalid_phone_number_count = 1
            composer.blocklisted_phone_number_count = blocklisted_phone_number_count
            composer.invalid_phone_number_count = invalid_phone_number_count

    @api.depends(lambda self: self._get_free_text_fields())
    def _compute_preview_whatsapp(self):
        """This method is used to compute the preview of the whatsapp message."""
        for record in self:
            rec = record._get_active_records()
            if record.wa_template_id and rec:
                record.preview_whatsapp = self.env['ir.qweb']._render('whatsapp.template_message_preview', {
                    'body': record._get_html_preview_whatsapp(rec=rec[0]),
                    'buttons': record.wa_template_id.button_ids,
                    'header_type': record.wa_template_id.header_type,
                    'footer_text': record.wa_template_id.footer_text,
                    'language_direction': 'rtl' if record.wa_template_id.lang_code in ('ar', 'he', 'fa', 'ur') else 'ltr',
                })
            else:
                record.preview_whatsapp = None

    @api.depends('wa_template_id')
    def _compute_number_of_free_text_button(self):
        for rec in self:
            tmpl_vars = rec.wa_template_id.variable_ids
            rec.number_of_free_text_button = len(tmpl_vars.filtered(lambda var: var.field_type == 'free_text' and var.line_type == 'button'))

    @api.depends('wa_template_id')
    def _compute_number_of_free_text(self):
        for rec in self:
            if rec.wa_template_id:
                rec.number_of_free_text = len(rec.wa_template_id.variable_ids.filtered(lambda line: line.field_type == 'free_text' and line.line_type == 'body'))
            else:
                rec.number_of_free_text = 0

    @api.depends('wa_template_id')
    def _compute_is_header_free_text(self):
        for rec in self:
            if rec.wa_template_id and rec.wa_template_id.variable_ids and rec.wa_template_id.variable_ids.filtered(lambda line: line.field_type == 'free_text' and line.line_type == 'header'):
                rec.is_header_free_text = True
            else:
                rec.is_header_free_text = False

    @api.depends('wa_template_id')
    def _compute_is_button_dynamic(self):
        for rec in self:
            if rec.wa_template_id and rec.wa_template_id.variable_ids and rec.wa_template_id.variable_ids.filtered(lambda line: line.field_type == 'free_text' and line.line_type == 'button'):
                rec.is_button_dynamic = True
            else:
                rec.is_button_dynamic = False

    def _extract_digits(self, string):
        if not string:
            return string
        matches = re.findall(r"\d+", string)
        result = "".join(matches)
        return result

    def _get_free_text_fields(self):
        return ["wa_template_id", "header_text_1", "button_dynamic_url_1", "button_dynamic_url_2"] + [f"free_text_{i}" for i in range(1, 11)]

    # ------------------------------------------------------------
    # SEND MESSAGES
    # ------------------------------------------------------------

    def action_send_whatsapp_template(self):
        self.ensure_one()
        if not self.wa_template_id:
            raise ValidationError(_("Please select a WhatsApp Template to send."))
        return self._send_whatsapp_template()

    def _create_whatsapp_messages_values(self, skip_raise_number=False):
        records = self._get_active_records()

        if self.wa_template_id and self.wa_template_id.variable_ids:
            field_types = self.wa_template_id.variable_ids.mapped('field_type')
            if 'user_phone' in field_types and not self.env.user.phone:
                raise ValidationError(
                    _("User phone number required in template but no value set on user profile.")
                )
        free_text_json = self._get_text_free_json()
        raise_exception = not (self.batch_mode or skip_raise_number)
        # batch compute of phone information
        use_default_recipient = self.wa_template_id.use_default_recipient
        recipients_phone_info = (
            records._phone_get_recipients_info() if use_default_recipient else {}
        )
        # (not entirely) batch compute of log recipients
        recipients = records._mail_get_partners()
        for record in records:
            if not recipients.get(record.id):
                recipients[record.id] = record._whatsapp_get_responsible().partner_id
        message_vals_all = []

        # setup a batch size to generate messages, independently from caller
        batch_size = self.env['ir.config_parameter'].sudo().get_int('mail.batch_size') or 50  # be sure to not have 0, as otherwise no iteration is done
        for batch_records in tools.split_every(batch_size, records.ids, piece_maker=records.browse):
            mobile_numbers, formatted_numbers_wa = [], []
            for rec in batch_records:
                mobile_number = None
                formatted_number_wa = None
                if self.batch_mode:
                    if use_default_recipient:
                        recipient_info = recipients_phone_info[rec.id]
                        # Format sanitized (E164) to WhatsApp format (e.g. 9163...)
                        formatted_number_wa = (
                            rec._whatsapp_phone_format(
                                number=recipient_info['sanitized'],
                                raise_on_format_error=raise_exception,
                            ) if recipient_info['sanitized'] else False
                        )
                        mobile_number = recipient_info['number']
                    elif self.wa_template_id.phone_field:
                        formatted_number_wa = rec._whatsapp_phone_format(
                            fpath=self.wa_template_id.phone_field,
                            raise_on_format_error=raise_exception,
                        )
                        mobile_number = rec.mapped(self.wa_template_id.phone_field)[0]
                elif not mobile_number:
                    mobile_number = self.phone
                    formatted_number_wa = rec._whatsapp_phone_format(
                        number=mobile_number, raise_on_format_error=raise_exception,
                    )
                mobile_numbers.append(mobile_number)
                formatted_numbers_wa.append(formatted_number_wa)

            # create linked mail.message records
            bodies = {rec.id: self._get_html_preview_whatsapp(rec=rec) for rec in batch_records}
            # unsupported batch on channel model due to their implementation
            if self.res_model == 'discuss.channel':
                messages = self.env['mail.message']
                for rec in batch_records:
                    messages += rec.message_post(body=bodies[rec.id], message_type="comment", subtype_xmlid='mail.mt_comment')
            elif hasattr(records, '_message_log'):
                messages = batch_records._message_log_batch(
                    bodies=bodies,
                    attachment_ids={rec.id: [self.attachment_id.id] if self.attachment_id else False for rec in batch_records},
                    message_type='whatsapp_message',
                    partner_ids={rec.id: recipients[rec.id].ids for rec in batch_records},
                )
            else:
                messages = self.env['mail.message'].create([
                    {
                        'body': bodies[rec.id],
                        'attachment_ids': self.attachment_id.ids,
                        'message_type': 'whatsapp_message',
                        'partner_ids': recipients[rec.id],
                        'res_id': rec.id,
                        'model': self.res_model,
                        'subtype_id': self.env['ir.model.data']._xmlid_to_res_id("mail.mt_note"),
                    } for rec in records
                ])

            for record, mobile_number, formatted_number_wa, message in zip(
                batch_records, mobile_numbers, formatted_numbers_wa, messages,
                strict=True,
            ):
                message_vals = {}
                if not formatted_number_wa:
                    message_vals.update({
                        'failure_type': 'phone_invalid',
                        'state': 'error',
                    })
                message_vals_all.append(message_vals | {
                    'mail_message_id': message.id,
                    'mobile_number': mobile_number,
                    'mobile_number_formatted': formatted_number_wa,
                    'free_text_json': free_text_json,
                    'wa_template_id': self.wa_template_id.id,
                    'wa_account_id': self.wa_template_id.wa_account_id.id,
                })
        return message_vals_all

    def _send_whatsapp_template(self, force_send_by_cron=False):
        messages_values = self._create_whatsapp_messages_values(skip_raise_number=force_send_by_cron)
        if messages_values:
            messages = self.env['whatsapp.message'].create(messages_values)
            messages._send(force_send_by_cron=force_send_by_cron)
            return messages
        return self.env["whatsapp.message"]

    def _get_text_free_json(self):
        """This method is used to prepare free text json using values set in free text field of composer."""
        self.ensure_one()
        json_vals = {}
        if self.header_text_1:
            json_vals['header_text'] = self.header_text_1
        if self.number_of_free_text:
            free_text_field = [f"free_text_{i + 1}" for i in range(self.number_of_free_text)]
            for value in free_text_field:
                if self[value]:
                    json_vals[value] = self[value]
        if self.button_dynamic_url_1:
            json_vals['button_dynamic_url_1'] = self.button_dynamic_url_1
        if self.button_dynamic_url_2:
            json_vals['button_dynamic_url_2'] = self.button_dynamic_url_2
        return json_vals

    def _get_html_preview_whatsapp(self, rec):
        """This method is used to get the html preview of the whatsapp message."""
        self.ensure_one()
        template_variables_value = self.wa_template_id.variable_ids._get_variables_value(rec)
        text_vars = self.wa_template_id.variable_ids.filtered(lambda var: var.field_type == 'free_text')
        body_text_vars = text_vars.filtered(lambda var: var.line_type == 'body')
        if self.wa_template_id.variable_type == 'named':
            body_text_vars = body_text_vars.sorted(key=lambda var: self.wa_template_id.body.find(var.name))
        else:
            body_text_vars = body_text_vars.sorted(key=lambda var: var._extract_variable_value())
        for var_index, body_text_var in zip(range(1, self.number_of_free_text + 1), body_text_vars):
            free_text_x = self[f'free_text_{var_index}']
            if free_text_x:
                template_variables_value[f'body-{body_text_var.name}'] = free_text_x
        header_text_var = text_vars.filtered(lambda var: var.line_type == 'header')
        if self.header_text_1 and header_text_var:
            template_variables_value[f'header-{header_text_var.name}'] = self.header_text_1
        return self.wa_template_id._get_formatted_body(variable_values=template_variables_value)

    # ------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------

    def _get_active_records(self):
        self.ensure_one()
        return self.env[self.res_model].browse(literal_eval(self.res_ids))
