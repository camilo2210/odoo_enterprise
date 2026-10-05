# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleCommissionAchievement(models.Model):
    _name = 'sale.commission.achievement'
    _description = 'Manual Commission Achievement'
    _order = 'id desc'

    add_user_id = fields.Many2one('res.users', "Add to", domain="[('share', '=', False)]")
    add_plan_id = fields.Many2one('sale.commission.plan', domain="[('state', '=', 'approved')]")
    reduce_user_id = fields.Many2one('res.users', "Reduce From", domain="[('share', '=', False)]")
    reduce_plan_id = fields.Many2one('sale.commission.plan', domain="[('state', '=', 'approved')]")
    achieved = fields.Monetary("Achieved", currency_field='currency_id')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False, default=lambda self: self.env.company)
    date = fields.Date("Date", default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    currency_rate = fields.Float(compute='_compute_currency_rate', store=True)
    note = fields.Char("Note")
    order_id = fields.Many2one('sale.order', "Linked Order", domain=[('state', '!=', 'cancel')])
    move_id = fields.Many2one('account.move', "Linked Invoice", domain=[('state', '!=', 'cancel'), ('move_type', 'in', ['out_invoice', 'out_refund'])])
    readonly = fields.Boolean(string="Locked", help="Lock records to prevent their modification (typically after running payroll). Only users with a high-enough access right can unlock records.", default=False)

    @api.constrains('add_user_id', 'add_plan_id', 'reduce_user_id', 'reduce_plan_id')
    def _constraints_users_plans(self):
        for achievement in self:
            add_values = bool(achievement.add_user_id) == bool(achievement.add_plan_id)
            reduce_values = bool(achievement.reduce_user_id) == bool(achievement.reduce_plan_id)
            if not add_values or not reduce_values:
                raise UserError(self.env._("Added values (user and plan) must be coherent: set or unset. Same for Reduced values"))

    @api.depends('note')
    def _compute_display_name(self):
        for achievement in self:
            if achievement.note:
                achievement.display_name = self.env._("Adjustment: %s", achievement.note)
            else:
                achievement.display_name = self.env._("Adjustment %s", achievement.id)

    @api.depends('currency_id', 'date')
    def _compute_currency_rate(self):
        for achievement in self:
            achievement.currency_rate = self.env['res.currency']._get_conversion_rate(
                    from_currency=achievement.company_id.currency_id,
                    to_currency=achievement.currency_id,
                    company=achievement.company_id,
                    date=achievement.date or fields.Date.context_today(achievement),
            )
