from odoo import api, fields, models
from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)


class EsgAction(models.Model):
    _name = 'esg.action'
    _description = 'ESG Action'
    _inherit = [
        'mail.thread',
        'mail.activity.mixin',
    ]

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, tracking=True)
    metric_id = fields.Many2one(
        'esg.metric', string='Metric', help="The CSRD metric associated with this action.", tracking=True, index='btree_not_null',
        falsy_value_label=_lt("No Metric"),
    )
    esrs_id = fields.Many2one('esg.esrs', string='ESRS', related='metric_id.esrs_id')
    tag_ids = fields.Many2many('esg.tag', string='Tags')
    priority = fields.Selection(
        string='Priority',
        selection=[
            ('0', 'Low priority'),
            ('1', 'Medium priority'),
            ('2', 'High priority'),
            ('3', 'Urgent'),
        ],
        default='0',
        tracking=True,
    )
    responsible_user_id = fields.Many2one('res.users', string='Responsible', help="The user responsible for this action.", tracking=True)
    company_id = fields.Many2one('res.company', help="The company to which this action applies. If not set, the action is considered applicable to all companies.")
    description = fields.Html(string='Description', help="A detailed description of the action.")
    measure_type = fields.Selection(
        selection=[
            ('physically', 'Physically (Quantity)'),
            ('monetary', 'Monetary'),
        ],
        required=True,
        default='physically',
        help="The approach used to express the baseline and target values, based on either a physical quantity or a monetary value.",
    )
    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure', compute='_compute_uom_id', store=True, readonly=False,
        help="The unit of measure used to express both the baseline and target values.", tracking=True,
    )
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', store=True, readonly=False, tracking=True)
    baseline_value = fields.Float(string='Baseline Value', help="The value of the metric at the baseline year.", tracking=True)
    baseline_start_date = fields.Date(string='Baseline Start Date', help="The start date used as a reference point to measure progress.", tracking=True)
    baseline_end_date = fields.Date(string='Baseline End Date', help="The end date used as a reference point to measure progress.", tracking=True)
    target_value = fields.Float(string='Target Value', help="The value the metric is expected to reach at the target year.", tracking=True)
    target_start_date = fields.Date(string='Target Start Date', help="The start date by which the target is expected to be achieved.", tracking=True)
    target_end_date = fields.Date(string='Target End Date', help="The end date by which the target is expected to be achieved.", tracking=True)
    value_history_ids = fields.One2many('esg.action.value.history', 'action_id', string='Value History', help="The historic record of measured values for this target.")
    current_value = fields.Float(compute='_compute_current_value', store=True, string='Current Value', help="The most recently recorded value, taken from the value history.")
    current_value_date = fields.Date(compute='_compute_current_value', store=True, string='Current Value Date', help="The date of the most recently recorded value.")
    has_target = fields.Boolean(compute='_compute_has_target', search='_search_has_target')
    is_reached = fields.Boolean(string='Reached', compute='_compute_is_reached', store=True, readonly=False, tracking=True)

    @api.depends('baseline_value', 'target_value', 'value_history_ids')
    def _compute_has_target(self):
        for action in self:
            action.has_target = bool(action.baseline_value or action.target_value or action.value_history_ids)

    def _search_has_target(self, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError
        want_has_target = value if operator == '=' else not value
        if want_has_target:
            return ['|', '|', ('baseline_value', '!=', 0), ('value_history_ids', '!=', False), ('target_value', '!=', 0)]
        return [('baseline_value', '=', 0), ('value_history_ids', '=', False), ('target_value', '=', 0)]

    @api.depends('baseline_value', 'target_value', 'current_value', 'value_history_ids')
    def _compute_is_reached(self):
        for action in self:
            if not action.has_target or not action.value_history_ids:
                action.is_reached = False
            elif action.target_value >= action.baseline_value:
                action.is_reached = action.current_value >= action.target_value
            else:
                action.is_reached = action.current_value <= action.target_value

    @api.depends('measure_type')
    def _compute_uom_id(self):
        for action in self:
            if action.measure_type == 'monetary':
                action.uom_id = False

    @api.depends('measure_type')
    def _compute_currency_id(self):
        for action in self:
            if action.measure_type == 'physically':
                action.currency_id = False

    @api.depends('value_history_ids.date', 'value_history_ids.value')
    def _compute_current_value(self):
        for action in self:
            latest_value = action.value_history_ids[:1]
            action.current_value = latest_value.value if latest_value else 0.0
            action.current_value_date = latest_value.date if latest_value else False

    def action_view_esg_metric(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'esg.metric',
            'res_id': self.metric_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
