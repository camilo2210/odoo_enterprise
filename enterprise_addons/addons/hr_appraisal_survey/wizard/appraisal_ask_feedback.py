# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError
from odoo.tools import html_sanitize, is_html_empty

_logger = logging.getLogger(__name__)


class AppraisalAskFeedback(models.TransientModel):
    _name = 'appraisal.ask.feedback'
    _inherit = ['mail.composer.mixin', 'hr.mixin']
    _description = "Ask Feedback for Appraisal"

    def _default_appraisal_id(self):
        active_id = self.env.context.get('active_id', None)
        if active_id:
            return active_id

        active_domain = self.env.context.get('active_domain', [])
        for d in active_domain:
            if isinstance(d, (list, tuple)) and len(d) == 3 and d[0] == 'appraisal_id':
                return d[2]
        return None

    appraisal_id = fields.Many2one('hr.appraisal', default=_default_appraisal_id)
    employee_id = fields.Many2one(related='appraisal_id.employee_id', string='Appraisal Employee')
    template_id = fields.Many2one(default=lambda self: self.env.ref('hr_appraisal_survey.mail_template_appraisal_ask_feedback', raise_if_not_found=False),
                                  domain=lambda self: [('model_id', '=', self.env['ir.model']._get('hr.appraisal').id)])
    attachment_ids = fields.Many2many(
        'ir.attachment', 'hr_appraisal_survey_mail_compose_message_ir_attachments_rel',
        'wizard_id', 'attachment_id', string='Attachments', bypass_search_access=True)
    author_id = fields.Many2one(
        'res.partner', string='Author', required=True,
        default=lambda self: self.env.user.partner_id.id,
    )
    allowed_survey_template_ids = fields.Many2many('survey.survey', compute='_compute_allowed_survey_template_ids')
    survey_template_id = fields.Many2one('survey.survey', required=True, compute='_compute_survey_template_id', compute_sudo=False, store=True,
                                         readonly=False, domain="[('id', 'in', allowed_survey_template_ids)]")
    partner_ids = fields.Many2many('res.partner', string="Recipients", required=True)
    deadline = fields.Date(string="Answer Deadline", required=True, compute='_compute_deadline', store=True, readonly=False)
    user_body = fields.Html('User Contents')

    # Overrides of mail.composer.mixin
    @api.depends('survey_template_id')  # fake trigger otherwise not computed in new mode
    def _compute_render_model(self):
        self.render_model = 'survey.user_input'

    @api.depends('employee_id')
    def _compute_subject(self):
        for wizard_su in self.filtered(lambda w: w.employee_id and w.template_id).sudo():
            wizard_su.subject = wizard_su.with_context(employee_id=wizard_su.employee_id)._render_template(
                wizard_su.template_id.subject,
                'hr.appraisal',
                wizard_su.appraisal_id.ids,
                engine='inline_template',
                options={'post_process': True}
            )[wizard_su.appraisal_id.id]

    @api.depends('template_id', 'partner_ids')
    def _compute_body(self):
        for wizard in self:
            langs = set(wizard.partner_ids.mapped('lang')) - {False}
            if len(langs) == 1:
                wizard = wizard.with_context(lang=langs.pop())
            super(AppraisalAskFeedback, wizard)._compute_body()

    @api.depends('appraisal_id')
    def _compute_allowed_survey_template_ids(self):
        all_appraisal_templates = self.env['survey.survey'].search([('survey_type', '=', 'appraisal')])
        for wizard in self:
            wizard.allowed_survey_template_ids = wizard.appraisal_id.appraisal_template_id.survey_template_ids or all_appraisal_templates

    @api.depends('allowed_survey_template_ids')
    def _compute_survey_template_id(self):
        for wizard in self:
            if not wizard.survey_template_id:
                wizard.survey_template_id = wizard.allowed_survey_template_ids[:1]

    @api.depends('appraisal_id.date_close')
    def _compute_deadline(self):
        for wizard in self:
            wizard.deadline = wizard.appraisal_id.date_close

    @api.onchange('template_id')
    def _onchange_template_id(self):
        self.attachment_ids = self.template_id.attachment_ids

    def _prepare_survey_answers(self, partners):
        answers = self.env['survey.user_input'].search([
            '&', '&',
            ('survey_id', '=', self.survey_template_id.id),
            ('appraisal_id', '=', self.appraisal_id.id),
            '|',
            '&', ('partner_id', 'in', partners.ids), ('partner_id', '!=', False),
            '&', ('email', 'in', partners.mapped('email')), ('email', '!=', False),
        ])
        new_or_updated_answers = answers.filtered(lambda l: l.deadline.date() != self.deadline)

        for new_partner in (partners - answers.partner_id):
            created_answer = self.survey_template_id.sudo()._create_answer(
                partner=new_partner, email=new_partner.email, check_attempts=False, deadline=self.deadline)
            new_or_updated_answers |= created_answer

        new_or_updated_answers.sudo().write({'appraisal_id': self.appraisal_id.id, 'deadline': self.deadline})
        return new_or_updated_answers

    def _send_mail(self, answer):
        """ Create mail specific for recipient containing notably its access token """
        ctx = {
            'logged_user': self.env.user.name,
            'employee': self.employee_id.name,
            'deadline': self.deadline,
            'user_body': self.user_body,
        }
        body = self.with_context(**ctx)._render_field('body', answer.ids)[answer.id]
        mail_values = {
            'email_from': self.author_id.email_formatted,
            'author_id': self.author_id.id,
            'model': None,
            'res_id': None,
            'subject': self.subject,
            'body_html': body,
            'attachment_ids': [(4, att.id) for att in self.attachment_ids],
            'auto_delete': True,
        }
        if answer.partner_id:
            mail_values['recipient_ids'] = [Command.link(answer.partner_id.id)]
        else:
            mail_values['email_to'] = answer.email

        mail_values['body_html'] = self.env['mail.render.mixin']._render_encapsulate(
            'mail.mail_notification_light', mail_values['body_html'],
            context_record=self.survey_template_id,
        )
        return self.env['mail.mail'].sudo().create(mail_values)

    def action_send(self):
        self.ensure_one()

        if fields.Date.context_today(self) > self.deadline:
            raise UserError(_("Please set an Answer Deadline in the future"))

        new_or_updated_answers = self._prepare_survey_answers(self.partner_ids)

        for survey_input in new_or_updated_answers:
            self._send_mail(survey_input)

        for partner in self.partner_ids.filtered(lambda p: p.employee and p.user_id and p.user_id.has_group('hr_appraisal.group_hr_appraisal_user')):
            answer = new_or_updated_answers.filtered(lambda l: l.partner_id == partner)
            if answer:
                self.appraisal_id.with_context(mail_activity_quick_update=True).activity_schedule(
                    'mail.mail_activity_data_todo', self.deadline,
                    summary=_('Fill the feedback form on survey'),
                    note=_('An appraisal feedback was requested. Please take time to fill the <a href="%s" target="_blank">survey</a>',
                        answer.get_start_url()),
                    user_id=partner.user_id.id)

        self.appraisal_id.partner_feedback_ids |= self.partner_ids
        self.appraisal_id.survey_ids |= self.survey_template_id
        return {'type': 'ir.actions.act_window_close'}

    def action_save_as_template(self):
        """ hit save as template button: current form value will be a new
            template attached to the current document. """
        model = self.env['ir.model']._get('hr.appraisal')
        template_name = _("Appraisal: Ask Feedback new template")
        for record in self:
            values = {
                'name': template_name,
                'subject': record.subject or False,
                'body_html': record.body or False,
                'model_id': model.id,
                'use_default_to': True,
            }
            template = self.env['mail.template'].create(values)

            if record.attachment_ids:
                attachments = record.env['ir.attachment'].sudo().browse(record.attachment_ids.ids).filtered(lambda a: a.create_uid.id == record.env.uid)
                if attachments:
                    attachments.write({'res_model': template._name, 'res_id': template.id})
                template.attachment_ids |= record.attachment_ids

            # generate the saved template
            record.write({'template_id': template.id})

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_id': template.id,
                'res_model': 'mail.template',
                'target': 'new',
            }
