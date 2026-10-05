# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.fields import Domain


class MarketingParticipant(models.Model):
    _name = 'marketing.participant'
    _description = 'Marketing Participant'
    _order = 'id ASC'
    _rec_name = 'resource_ref'

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if 'res_id' in fields and not defaults.get('res_id'):
            model_name = defaults.get('model_name')
            if not model_name and defaults.get('campaign_id'):
                model_name = self.env['marketing.campaign'].browse(defaults['campaign_id']).model_name
            if model_name and model_name in self.env:
                resource = self.env[model_name].search([], limit=1)
                defaults['res_id'] = resource.id
        return defaults

    @api.model
    def _selection_target_model(self):
        models = self.env['ir.model'].sudo().search([('is_mail_thread', '=', True)])
        return [(model.model, model.name) for model in models]

    campaign_id = fields.Many2one(
        'marketing.campaign', string='Campaign',
        index=True, ondelete='cascade', required=True)
    model_id = fields.Many2one(
        'ir.model', string='Model', related='campaign_id.model_id',
        index=True, readonly=True, store=True)
    model_name = fields.Char(
        string='Record model', related='campaign_id.model_id.model',
        readonly=True, store=True)
    # TDE note: somehow make it required + cleanup leftover ?
    res_id = fields.Integer(string='Record ID', index=True)
    resource_ref = fields.Reference(
        string='Record', selection='_selection_target_model',
        compute='_compute_resource_ref', inverse='_set_resource_ref', search='_search_resource_ref')
    trace_ids = fields.One2many('marketing.trace', 'participant_id', string='Actions')
    state = fields.Selection([
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
        ('rejected', 'Rejected'),  # being out of campaign's enroll_domain filter
        ('unlinked', 'Unlinked'),  # record found to be unlinked
        ], default='running', index=True, required=True,
        help='Removed means the related record does not exist anymore.')
    is_test = fields.Boolean('Test Record', default=False)
    # enroll information
    # anniversary-specific enroll date, different from create_date to ease usage
    anniversary_dt = fields.Datetime(string='Enrolled at')

    @api.depends('model_name', 'res_id')
    def _compute_resource_ref(self):
        for participant in self:
            if participant.model_name and participant.model_name in self.env:
                participant.resource_ref = '%s,%s' % (participant.model_name, participant.res_id or 0)
            else:
                participant.resource_ref = None

    def _set_resource_ref(self):
        for participant in self:
            if participant.resource_ref:
                participant.res_id = participant.resource_ref.id

    def _search_resource_ref(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        ir_model_ids = []
        for [model_name] in self.env['marketing.campaign']._read_group([], ['model_name']):
            model = self.env.get(model_name)
            if model is None:
                continue
            ir_model_ids += self.env['marketing.participant'].search(
                ['&', ('model_name', '=', model_name), ('res_id', 'in', [name[0] for name in model.name_search(name=value)])],
                order='id',
            ).ids
        return [('id', 'in', ir_model_ids)]

    # STATE MANAGEMENT
    # ------------------------------------------------------------

    def check_completed(self):
        existing_traces = self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', 'in', ['scheduled', 'waiting']),
        ])
        (self - existing_traces.mapped('participant_id')).write({'state': 'completed'})

    def action_set_canceled(self, trace_message: str | None = None):
        """ Cancel current participants and their scheduled traces """
        self.write({'state': 'canceled'})
        return self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled'),
        ]).action_set_canceled(message=trace_message or self.env._('Participant canceled'), check_participant_completed=False)

    def action_set_completed_manual(self):
        """ Manually mark as a completed and cancel every scheduled trace """
        return self.action_set_completed(trace_message=_('Marked as completed'))

    def action_set_completed(self, trace_message: str | None = None):
        """ Mark as completed, and cancel their scheduled traces. """
        self.write({'state': 'completed'})
        return self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled'),
        ]).action_set_canceled(message=trace_message, check_participant_completed=False)

    def action_set_running(self):
        return self.write({'state': 'running'})

    def action_set_rejected(self, trace_message: str | None = None):
        """ Mark related record has been unlinked """
        self.write({'state': 'rejected'})
        return self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled'),
        ]).action_set_canceled(message=trace_message or self.env._('Record rejected from campaign'), check_participant_completed=False)

    def action_set_unlinked(self, trace_message: str | None = None):
        """ Mark related record has been unlinked """
        self.write({'state': 'unlinked'})
        return self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled'),
        ]).action_set_canceled(message=trace_message or self.env._('Record deleted'), check_participant_completed=False)
