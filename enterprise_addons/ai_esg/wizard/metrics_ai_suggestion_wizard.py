from odoo import api, fields, models


class MetricsAiSuggestionWizard(models.TransientModel):
    _name = 'metrics.ai.suggestion.wizard'
    _description = 'AI suggestions of ESG Metrics'

    suggestion_line_ids = fields.One2many('metrics.ai.suggestion.line', 'wizard_id')
    has_one_or_more_selected = fields.Boolean(compute='_compute_has_one_or_more_selected')

    @api.depends('suggestion_line_ids.is_selected')
    def _compute_has_one_or_more_selected(self):
        for wizard in self:
            wizard.has_one_or_more_selected = any(wizard.suggestion_line_ids.mapped('is_selected'))

    def action_add_suggestions(self):
        self.ensure_one()
        metric_vals = [
            {
                'name': line.name,
                'esrs_id': line.esrs_id.id,
                'type': line.type,
                'category': line.category,
                'notes': line.detail,
            }
            for line in self.suggestion_line_ids
            if line.is_selected or self.env.context.get('add_all_suggestions')
        ]
        if metric_vals:
            self.env['esg.metric'].create(metric_vals)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': self.env._('Metrics have been successfully created.'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        return {'type': 'ir.actions.act_window_close'}


class MetricsAiSuggestionLine(models.TransientModel):
    _name = 'metrics.ai.suggestion.line'
    _description = 'AI suggestion of ESG Metric'

    wizard_id = fields.Many2one('metrics.ai.suggestion.wizard', required=True)
    is_selected = fields.Boolean()
    esrs_id = fields.Many2one('esg.esrs', required=True)
    code = fields.Char(related='esrs_id.code')
    name = fields.Char()
    type = fields.Selection(
        selection=[
            ('positive_impact', 'Positive Impact'),
            ('negative_impact', 'Negative Impact'),
            ('risk', 'Risk'),
            ('opportunity', 'Opportunity'),
        ],
        required=True,
        readonly=True,
    )
    category = fields.Selection(related='esrs_id.category')
    detail = fields.Text()
