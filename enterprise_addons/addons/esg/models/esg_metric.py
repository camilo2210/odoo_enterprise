from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError


class EsgMetric(models.Model):
    _name = 'esg.metric'
    _description = 'Metric'
    _inherit = [
        'mail.thread',
    ]

    def _get_score_selection(self):
        return [
            ('1', 'Negligible'),
            ('2', 'Low'),
            ('3', 'Moderate'),
            ('4', 'High'),
            ('5', 'Critical'),
        ]

    def _get_default_dates(self):
        return self.env['res.company'].sudo().ESG_REPORT_DEFAULT_COMPANY.compute_fiscalyear_dates(fields.Date.context_today(self))

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    status = fields.Selection(
        selection=[
            ('actual', 'Actual'),
            ('potential', 'Potential'),
        ],
        help='Indicates whether the metric reflects a situation that has already occurred (Actual) or one that may occur in the future (Potential).',
    )
    priority = fields.Selection(
        string='Priority',
        selection=[
            ('0', 'Low priority'),
            ('1', 'Medium priority'),
            ('2', 'High priority'),
            ('3', 'Urgent'),
        ],
        default='0',
        compute='_compute_priority',
        store=True,
    )
    esrs_id = fields.Many2one('esg.esrs', 'ESRS', required=True)
    category = fields.Selection(related='esrs_id.category')
    esrs_section = fields.Char(related='esrs_id.section')
    esrs_code = fields.Char(related='esrs_id.code')
    type = fields.Selection(
        string='Type',
        selection=[
            ('positive_impact', 'Positive Impact'),
            ('negative_impact', 'Negative Impact'),
            ('risk', 'Risk'),
            ('opportunity', 'Opportunity'),
        ],
        required=True,
    )
    company_id = fields.Many2one('res.company')
    tag_ids = fields.Many2many('esg.tag', string='Tags')
    date_start = fields.Date(
        string='Reporting Date',
        default=lambda self: self._get_default_dates()['date_from'],
    )
    date_end = fields.Date(
        string='Reporting End Date',
        default=lambda self: self._get_default_dates()['date_to'],
    )
    materiality_type = fields.Selection(
        string='Materiality',
        selection=[
            ('non_material', 'Non-Material'),
            ('financial', 'Financial Material'),
            ('impact', 'Impact Material'),
            ('double', 'Double Material'),
        ],
        compute='_compute_materiality_type',
        store=True,
    )
    materiality_type_color = fields.Integer(compute='_compute_materiality_type_color', export_string_translation=False)
    gap_analysis = fields.Selection(
        string='Gap Analysis',
        selection=[
            ('available', 'Available'),
            ('missing', 'Missing'),
        ],
        help='Indicates if data for this metric/DR is available.\n'
             'Available: data exists and ready to report.\n'
             'Missing: data needs to be collected or actions taken to make it available.'
    )
    justification = fields.Text(
        string='Justification',
        help='For topics marked as immaterial, a clear explanation is required to support transparency in the CSRD report. '
             'For material topics, providing a justification is recommended as it adds valuable context.',
    )
    notes = fields.Html()
    attachment_ids = fields.One2many(
        'ir.attachment',
        compute='_compute_attachment_ids',
        string='Documents (PDF)',
        readonly=False,
    )
    action_ids = fields.One2many('esg.action', 'metric_id', string='Actions')
    action_count = fields.Integer(compute='_compute_action_count', export_string_translation=False)
    reached_action_count = fields.Integer(compute='_compute_action_count', export_string_translation=False)

    # Score fields
    impact_severity_score = fields.Selection(
        string='Impact Severity',
        selection=lambda self: self._get_score_selection(),
        compute='_compute_impact_severity_score',
        readonly=False,
        store=True,
        tracking=True,
        help='How significant this metric is for people or the environment?',
    )
    display_impact_severity_score = fields.Selection(
        selection=lambda self: self._get_score_selection(),
        compute='_compute_display_impact_severity_score',
        export_string_translation=False,
        help='How significant this metric is for people or the environment?',
    )
    scale_value = fields.Selection(
        string='Scale',
        selection=lambda self: self._get_score_selection(),
        help='How critical are the impacts caused by this activity on people or environment?',
    )
    scope_value = fields.Selection(
        string='Scope',
        selection=lambda self: self._get_score_selection(),
        help='How widespread are the impacts caused by this activity?',
    )
    remediability_value = fields.Selection(
        string='Remediability',
        selection=lambda self: self._get_score_selection(),
        help='How easy is to fix or reverse the impacts once it occurs?',
    )
    financial_severity_score = fields.Selection(
        string='Financial Severity',
        selection=lambda self: self._get_score_selection(),
        compute='_compute_financial_severity_score',
        readonly=False,
        store=True,
        tracking=True,
        help='How significant this metric is for the company\'s finances?',
    )
    display_financial_severity_score = fields.Selection(
        selection=lambda self: self._get_score_selection(),
        compute='_compute_display_financial_severity_score',
        export_string_translation=False,
        help='How significant this metric is for the company\'s finances?',
    )
    financial_impacts_value = fields.Selection(
        string='Financial Impacts',
        selection=lambda self: self._get_score_selection(),
        help='If these impacts occur, how large could the financial effects be?',
    )
    likelihood_value = fields.Selection(
        string='Likelihood',
        selection=[
            ('1', 'Very Unlikely'),
            ('2', 'Unlikely'),
            ('3', 'Possible'),
            ('4', 'Likely'),
            ('5', 'Almost Certain'),
        ],
        help='How likely is this financial effect to occur?',
    )
    stakeholder_impact_severity_score = fields.Selection(
        string='Stakeholder Impact Severity Score',
        selection=lambda self: self._get_score_selection(),
        compute='_compute_stakeholder_impact_severity_score',
        readonly=False,
        store=True,
        tracking=True,
        help='Average impact score given by stakeholders for this metric.',
    )
    stakeholder_financial_severity_score = fields.Selection(
        string='Stakeholder Financial Severity Score',
        selection=lambda self: self._get_score_selection(),
        compute='_compute_stakeholder_financial_severity_score',
        readonly=False,
        store=True,
        tracking=True,
        help='Average financial score given by stakeholders for this metric.',
    )
    is_stakeholder_impact_score_manually_edited = fields.Boolean(export_string_translation=False)
    is_stakeholder_financial_score_manually_edited = fields.Boolean(export_string_translation=False)
    has_significant_impact_score_gap = fields.Boolean(compute='_compute_has_significant_impact_score_gap', export_string_translation=False)
    has_significant_financial_score_gap = fields.Boolean(compute='_compute_has_significant_financial_score_gap', export_string_translation=False)
    score_gap_warning_message = fields.Char(compute='_compute_score_gap_warning_message', export_string_translation=False)

    # Survey fields
    survey_ids = fields.Many2many('survey.survey', help='Sent out Surveys')
    survey_answer_count = fields.Integer(compute='_compute_survey_answer_statistic')
    survey_answer_done_count = fields.Integer(compute='_compute_survey_answer_statistic')

    @api.depends('type', 'status')
    def _compute_impact_severity_score(self):
        for metric in self:
            if not metric.impact_severity_score:
                continue
            metric.impact_severity_score = metric._get_impact_severity_score()

    @api.depends('scale_value', 'scope_value', 'remediability_value', 'likelihood_value', 'type', 'status')
    def _compute_display_impact_severity_score(self):
        for metric in self:
            metric.display_impact_severity_score = metric._get_impact_severity_score()

    @api.depends('status')
    def _compute_financial_severity_score(self):
        for metric in self:
            if not metric.financial_severity_score:
                continue
            metric.financial_severity_score = metric._get_financial_severity_score()

    @api.depends('financial_impacts_value', 'likelihood_value', 'status')
    def _compute_display_financial_severity_score(self):
        for metric in self:
            metric.display_financial_severity_score = metric._get_financial_severity_score()

    @api.depends('impact_severity_score', 'financial_severity_score')
    def _compute_materiality_type(self):
        non_negligable_scores = ['3', '4', '5']
        for metric in self:
            is_high_financial = metric.financial_severity_score in non_negligable_scores
            if metric.impact_severity_score in non_negligable_scores:
                metric.materiality_type = 'double' if is_high_financial else 'impact'
            else:
                metric.materiality_type = 'financial' if is_high_financial else 'non_material'

    @api.depends('materiality_type')
    def _compute_materiality_type_color(self):
        materiality_type_color = {
            'impact': 2,  # orange
            'financial': 2,  # orange
            'double': 1,  # red / danger
            'non_material': 0,
            False: 0,  # default grey -- for studio
        }
        for metric in self:
            metric.materiality_type_color = materiality_type_color[metric.materiality_type]

    @api.depends('materiality_type', 'gap_analysis')
    def _compute_priority(self):
        for metric in self:
            if metric.materiality_type == 'non_material':
                metric.priority = '0'
                continue
            is_double_material = metric.materiality_type == 'double'
            if metric.gap_analysis == 'missing':
                metric.priority = '3' if is_double_material else '2'
            elif is_double_material:
                metric.priority = '2'
            else:
                metric.priority = '1'

    def _compute_attachment_ids(self):
        for metric in self:
            attachment_ids = self.env['ir.attachment'].search([('res_id', '=', metric.id), ('res_model', '=', 'esg.metric')]).ids
            message_attachment_ids = metric.mapped('message_ids.attachment_ids').ids  # from mail_thread
            metric.attachment_ids = [(6, 0, list(set(attachment_ids) - set(message_attachment_ids)))]

    @api.depends('action_ids.is_reached')
    def _compute_action_count(self):
        counts = self.env['esg.action']._read_group(
            [('metric_id', 'in', self.ids)],
            ['metric_id', 'is_reached'],
            ['__count'],
        )
        action_count = defaultdict(int)
        reached_action_count = defaultdict(int)
        for metric, is_reached, count in counts:
            action_count[metric.id] += count
            if is_reached:
                reached_action_count[metric.id] += count
        for metric in self:
            metric.action_count = action_count[metric.id]
            metric.reached_action_count = reached_action_count[metric.id]

    @api.depends('survey_ids.user_input_ids.state', 'survey_ids.user_input_ids.user_input_line_ids')
    def _compute_stakeholder_impact_severity_score(self):
        score_per_metric = {}
        for metric, questions in self.env['esg.metric.to.survey.question']._read_group(
            domain=[('metric_id', 'in', self.ids), ('metric_score_type', '=', 'impact')],
            groupby=['metric_id'],
            aggregates=['question_id:recordset'],
        ):
            result = self.env['survey.user_input.line']._read_group(
                domain=[('user_input_id.state', '=', 'done'), ('question_id', 'in', questions.ids)],
                aggregates=['answer_score:avg'],
            )
            if result:
                score_per_metric[metric] = result[0][0]

        for metric in self:
            score = score_per_metric.get(metric, 0.0)
            if score:
                if score <= 1:
                    metric.stakeholder_impact_severity_score = '1'
                elif score <= 2:
                    metric.stakeholder_impact_severity_score = '2'
                elif score <= 3:
                    metric.stakeholder_impact_severity_score = '3'
                elif score <= 4:
                    metric.stakeholder_impact_severity_score = '4'
                else:
                    metric.stakeholder_impact_severity_score = '5'
            else:
                metric.stakeholder_impact_severity_score = False

    @api.depends('survey_ids.user_input_ids.state', 'survey_ids.user_input_ids.user_input_line_ids')
    def _compute_stakeholder_financial_severity_score(self):
        score_per_metric = {}
        for metric, questions in self.env['esg.metric.to.survey.question']._read_group(
            domain=[('metric_id', 'in', self.ids), ('metric_score_type', '=', 'financial')],
            groupby=['metric_id'],
            aggregates=[('question_id:recordset')],
        ):
            result = self.env['survey.user_input.line']._read_group(
                domain=[('user_input_id.state', '=', 'done'), ('question_id', 'in', questions.ids)],
                aggregates=['answer_score:avg'],
            )
            if result:
                score_per_metric[metric] = result[0][0]

        for metric in self:
            score = score_per_metric.get(metric, 0.0)
            if score:
                if score <= 1:
                    metric.stakeholder_financial_severity_score = '1'
                elif score <= 2:
                    metric.stakeholder_financial_severity_score = '2'
                elif score <= 3:
                    metric.stakeholder_financial_severity_score = '3'
                elif score <= 4:
                    metric.stakeholder_financial_severity_score = '4'
                else:
                    metric.stakeholder_financial_severity_score = '5'
            else:
                metric.stakeholder_financial_severity_score = False

    @api.model
    def _has_significant_score_gap(self, score, stakeholder_score):
        return bool(score) and bool(stakeholder_score) and abs(int(score) - int(stakeholder_score)) > 2

    @api.depends('impact_severity_score', 'stakeholder_impact_severity_score')
    def _compute_has_significant_impact_score_gap(self):
        for metric in self:
            metric.has_significant_impact_score_gap = self._has_significant_score_gap(
                metric.impact_severity_score, metric.stakeholder_impact_severity_score
            )

    @api.depends('financial_severity_score', 'stakeholder_financial_severity_score')
    def _compute_has_significant_financial_score_gap(self):
        for metric in self:
            metric.has_significant_financial_score_gap = self._has_significant_score_gap(
                metric.financial_severity_score, metric.stakeholder_financial_severity_score
            )

    @api.depends('has_significant_impact_score_gap', 'has_significant_financial_score_gap')
    def _compute_score_gap_warning_message(self):
        for metric in self:
            if metric.has_significant_impact_score_gap and metric.has_significant_financial_score_gap:
                scope = self.env._('impact and financial severity scores')
            elif metric.has_significant_impact_score_gap:
                scope = self.env._('impact severity score')
            elif metric.has_significant_financial_score_gap:
                scope = self.env._('financial severity score')
            else:
                metric.score_gap_warning_message = False
                continue
            metric.score_gap_warning_message = self.env._(
                'There is a significant difference between the stakeholder %(scope)s and yours. This may be worth reviewing.',
                scope=scope,
            )

    @api.depends('survey_ids')
    def _compute_survey_answer_statistic(self):
        user_input_read_group = self.env['survey.user_input']._read_group(
            [('survey_id', 'in', self.survey_ids.ids)],
            ['survey_id', 'state'],
            ['__count'],
        )
        stat_per_survey = defaultdict(lambda: {'answer_done_count': 0, 'answer_count': 0})
        for survey, state, count in user_input_read_group:
            stat_per_survey[survey]['answer_count'] += count
            if state == 'done':
                stat_per_survey[survey]['answer_done_count'] += count
        for metric in self:
            answer_count = answer_done_count = 0
            for survey in metric.survey_ids:
                answer_count += stat_per_survey[survey]['answer_count']
                answer_done_count += stat_per_survey[survey]['answer_done_count']
            metric.survey_answer_count = answer_count
            metric.survey_answer_done_count = answer_done_count

    def _get_impact_severity_score(self):
        self.ensure_one()
        scores = [int(self.scale_value), int(self.scope_value)]
        if self.type not in ['positive_impact', 'opportunity']:
            scores.append(int(self.remediability_value))
        if self.status != 'actual':
            scores.append(int(self.likelihood_value))
        score = sum(scores) / len(scores)
        if 0 <= score < 1:
            return '1'
        elif 1 <= score < 2:
            return '2'
        elif 2 <= score < 3:
            return '3'
        elif 3 <= score < 4:
            return '4'
        else:
            return '5'

    def _get_financial_severity_score(self):
        scores = [int(self.financial_impacts_value)]
        if self.status != 'actual':
            scores.append(int(self.likelihood_value))
        score = sum(scores) / len(scores)
        if 0 <= score < 1:
            return '1'
        elif 1 <= score < 2:
            return '2'
        elif 2 <= score < 3:
            return '3'
        elif 3 <= score < 4:
            return '4'
        else:
            return '5'

    def action_view_esg_actions(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('esg.action_view_esg_action')
        action['domain'] = [('metric_id', '=', self.id)]
        action['context'] = {'default_metric_id': self.id}
        return action

    def action_open_impact_severity_score(self):
        self.ensure_one()
        return {
            'name': self.env._('%(name)s Impact Severity Assessement', name=self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'esg.metric',
            'target': 'new',
            'views': [(self.env.ref('esg.esg_metric_impact_severity_score_form_view').id, 'form')],
            'res_id': self.id,
        }

    def action_save_impact_scores(self):
        self.ensure_one()
        self.impact_severity_score = self.display_impact_severity_score

    def action_open_financial_severity_score(self):
        self.ensure_one()
        return {
            'name': self.env._('%(name)s Financial Severity Assessement', name=self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'esg.metric',
            'target': 'new',
            'views': [(self.env.ref('esg.esg_metric_financial_severity_score_form_view').id, 'form')],
            'res_id': self.id,
        }

    def action_save_financial_scores(self):
        self.ensure_one()
        self.financial_severity_score = self.display_financial_severity_score

    def action_ask_stakeholder_review(self):
        if not (self.env.user.has_group('survey.group_survey_user') and self.env.user.has_group('esg.esg_group_manager')):
            raise UserError(self.env._('You need ESG manager and Survey user access rights in order to access this action.'))
        metrics = self
        if not metrics:
            fiscal_year_dates = self.env['res.company'].sudo().ESG_REPORT_DEFAULT_COMPANY.compute_fiscalyear_dates(fields.Date.context_today(self))
            metrics = self.search([('date_start', '<=', fiscal_year_dates['date_to']), ('date_end', '>=', fiscal_year_dates['date_from'])])
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'esg.metric.ask.feedback',
            'target': 'new',
            'name': self.env._('Stakeholder Review'),
            'context': {
                'default_metric_ids': metrics.ids,
            }
        }

    def action_open_metric_survey_input_lines(self):
        self.ensure_one()
        if not (self.env.user.has_group('survey.group_survey_user') and self.env.user.has_group('esg.esg_group_manager')):
            raise UserError(self.env._('You need ESG manager and Survey user access rights in order to access this action.'))
        view_id = self.env.ref('esg.esg_survey_user_input_view_list', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'survey.user_input',
            'name': self.env._('Stakeholder Reviews'),
            'views': [[view_id.id, 'list'], [False, 'form']],
            'domain': [('survey_id', 'in', self.survey_ids.ids)],
        }

    def action_apply_stakeholder_impact_score(self):
        self.ensure_one()
        self._compute_stakeholder_impact_severity_score()
        self.is_stakeholder_impact_score_manually_edited = False

    def action_apply_stakeholder_financial_score(self):
        self.ensure_one()
        self._compute_stakeholder_financial_severity_score()
        self.is_stakeholder_financial_score_manually_edited = False
