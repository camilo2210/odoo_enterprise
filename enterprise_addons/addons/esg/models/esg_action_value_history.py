from odoo import fields, models


class EsgActionValueHistory(models.Model):
    _name = 'esg.action.value.history'
    _description = 'ESG Action Target Value History'
    _order = 'date desc, id desc'

    action_id = fields.Many2one('esg.action', string='Action', required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    value = fields.Float(string='Value', required=True)
