from odoo import api, fields, models, Command
from odoo.exceptions import UserError


class EsgMetricAskFeedback(models.TransientModel):
    _name = 'esg.metric.ask.feedback'
    _inherit = ['mail.composer.mixin']
    _description = "Stakeholder Reviews for CSRD Metrics"

    metric_ids = fields.One2many('esg.metric', compute='_compute_metric_ids', required=True)
    template_id = fields.Many2one(default=lambda self: self.env.ref('esg.mail_template_esg_metric_ask_feedback', raise_if_not_found=False),
                                  domain=lambda self: [('model_id', '=', self.env['ir.model']._get('esg.metric').id)])
    author_id = fields.Many2one(
        'res.partner', string='Author', required=True,
        default=lambda self: self.env.user.partner_id.id,
    )
    survey_template_id = fields.Many2one('survey.survey')
    partner_ids = fields.Many2many('res.partner', string="Stakeholders", required=True)
    deadline = fields.Date(string="Answer Deadline", required=True)

    @api.depends_context('default_metric_ids')
    def _compute_metric_ids(self):
        metric_ids = self.env.context.get('default_metric_ids', [])
        self.metric_ids = self.env['esg.metric'].browse(metric_ids)

    # Overrides of mail.composer.mixin
    @api.depends('survey_template_id')  # fake trigger otherwise not computed in new mode
    def _compute_render_model(self):
        self.render_model = 'survey.user_input'

    @api.depends('metric_ids')
    def _compute_subject(self):
        for wizard in self.filtered(lambda w: w.metric_ids and w.template_id):
            wizard.subject = self.env._(
                'Invitation to Participate in CSRD Double Materiality Stakeholder Review for %(company_name)s Company',
                company_name=self.env.company.name,
            )

    @api.depends('template_id', 'partner_ids')
    def _compute_body(self):
        for wizard in self:
            langs = set(wizard.partner_ids.mapped('lang')) - {False}
            if len(langs) == 1:
                wizard = wizard.with_context(lang=langs.pop())
            super(EsgMetricAskFeedback, wizard)._compute_body()

    @api.onchange('partner_ids')
    def _onchange_partner_ids(self):
        emailless_partners = self.partner_ids.filtered(lambda p: not p.email)
        if emailless_partners:
            warning = {
                'title': self.env._('Missing email'),
                'message': self.env._('The following partners do not have any email: \n%s',
                        ', '.join(emailless_partners.mapped('name'))),
                'type': 'notification',
            }
            self.partner_ids = self.partner_ids - emailless_partners
            return {'warning': warning}

    def _prepare_survey_anwers(self, partners):
        answers = self.env['survey.user_input']
        partners_info = partners.mapped(lambda partner: {
            'id': partner.id,
            'email': partner.email,
            'partner_id': partner,
        })
        emails = [p['email'] for p in partners_info]
        partner_ids = [p['id'] for p in partners_info]

        if not self.survey_template_id:
            survey_template_id = self.env.ref('esg.esg_metric_review_template', raise_if_not_found=False)
            if not survey_template_id:
                raise UserError(self.env._('No Metric Review Survey Template found.'))
            self.survey_template_id = survey_template_id.copy()
            self.survey_template_id.title = "Stakeholder Review for CSRD Report"
            self.survey_template_id.user_id = self.env.user.id
            questions_create_vals = []
            metric_to_question_create_vals = []
            iro_type_labels = dict(self.env['esg.metric']._fields['type']._description_selection(self.env))
            sequence = 1
            for metric_type, metrics in self.metric_ids.sorted('esrs_id').grouped('type').items():
                for metric in metrics:
                    questions_create_vals.append({
                        'survey_id': self.survey_template_id.id,
                        'title': f'{iro_type_labels[metric_type]}: {metric.name}',
                        'is_page': True,
                        'sequence': sequence,
                    })
                    sequence += 1
                    question_vals = {
                        'survey_id': self.survey_template_id.id,
                        'question_type': 'simple_choice',
                        'constr_mandatory': True,
                        'suggested_answer_ids': [
                            Command.create({'value': 'Negligible', 'sequence': 1, 'answer_score': 1.0}),
                            Command.create({'value': 'Low', 'sequence': 2, 'answer_score': 2.0}),
                            Command.create({'value': 'Moderate', 'sequence': 3, 'answer_score': 3.0}),
                            Command.create({'value': 'High', 'sequence': 4, 'answer_score': 4.0}),
                            Command.create({'value': 'Critical', 'sequence': 5, 'answer_score': 5.0}),
                        ],
                    }
                    question = self.env['survey.question'].sudo().create({
                        **question_vals,
                        'title': f'How critical is the {iro_type_labels[metric_type]} of {metric.name} on people and environment impacted by your activities?',
                        'sequence': sequence,
                    })
                    metric_to_question_create_vals.append({
                        'metric_id': metric.id,
                        'question_id': question.id,
                        'metric_score_type': 'impact',
                    })
                    sequence += 1
                    title_part = ''
                    if metric_type == 'opportunity':
                        title_part = 'developing this opportunity'
                    elif metric_type == 'risk':
                        title_part = 'facing that risk'
                    else:
                        title_part = 'being exposed to this impact'
                    question = self.env['survey.question'].sudo().create({
                        **question_vals,
                        'title': f'What would be the financial impact on your company of {title_part}?',
                        'sequence': sequence,
                    })
                    metric_to_question_create_vals.append({
                        'metric_id': metric.id,
                        'question_id': question.id,
                        'metric_score_type': 'financial',
                    })
                    sequence += 1
                    questions_create_vals.append({
                        'survey_id': self.survey_template_id.id,
                        'title': 'Comments (optional)',
                        'question_type': 'text_box',
                        'question_placeholder': 'Explain your rating or provide context',
                        'sequence': sequence,
                    })
                    sequence += 1
            self.env['survey.question'].sudo().create(questions_create_vals)
            self.env['esg.metric.to.survey.question'].create(metric_to_question_create_vals)

        existing_metric_to_questions = self.env['esg.metric.to.survey.question'].search([
            ('metric_id', 'in', self.metric_ids.ids),
        ])
        existing_answers = self.env['survey.user_input'].search([
            ('user_input_line_ids.question_id', 'in', existing_metric_to_questions.question_id.ids),
            '|',
            '&', ('partner_id', 'in', partner_ids), ('partner_id', '!=', False),
            '&', ('email', 'in', emails), ('email', '!=', False),
        ])
        partners_done = []
        if existing_answers:
            existing_answer_emails = existing_answers.filtered('email').mapped('email')
            existing_answer_partners_id = existing_answers.filtered('partner_id').mapped('partner_id')
            for partner_data in partners_info:
                if partner_data.get('email') in existing_answer_emails or partner_data.get('partner_id') in existing_answer_partners_id:
                    partners_done.append(partner_data)
            existing_answers = existing_answers.sorted(lambda answer: answer.create_date, reverse=True)
            for partner_done in partners_done:
                answers |= existing_answers\
                    .filtered(lambda a:
                        (a.partner_id and a.partner_id == partner_done.get('partner_id'))
                        or (a.email and a.email == partner_done.get('email'))
                    )[:1]

        partners_done_ids = [p['id'] for p in partners_done]
        for new_partner in partners_info:
            if new_partner['id'] in partners_done_ids:
                continue
            answers |= self.survey_template_id.sudo()._create_answer(
                partner=new_partner['partner_id'], email=new_partner['email'], check_attempts=False, deadline=self.deadline)
        return answers

    def _send_mail(self, answer):
        """ Create mail specific for recipient containing notably its access token """
        ctx = {
            'logged_user': self.env.user.name,
            'company_name': self.env.company.name,
            'deadline': self.deadline,
        }
        body = self.with_context(**ctx)._render_field('body', answer.ids)[answer.id]
        mail_values = {
            'email_from': self.author_id.email_formatted,
            'author_id': self.author_id.id,
            'model': None,
            'res_id': None,
            'subject': self.subject,
            'body_html': body,
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
            raise UserError(self.env._("Please set an Answer Deadline in the future"))

        answers = self._prepare_survey_anwers(self.partner_ids)
        answers.sudo().write({'deadline': self.deadline})
        for answer in answers:
            self._send_mail(answer)

        for metric in self.metric_ids:
            metric.survey_ids |= self.survey_template_id
            metric.message_post(body=self.env._(
                "A new Stakeholder Review was requested for %s", ', '.join(self.partner_ids.mapped('name'))
            ))
        return {'type': 'ir.actions.act_window_close'}
