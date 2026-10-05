# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, models, fields
from odoo.exceptions import ValidationError


class SaleCommissionPlanTarget(models.Model):
    _name = 'sale.commission.plan.target'
    _description = 'Commission Plan Target'
    _order = 'id'

    plan_id = fields.Many2one('sale.commission.plan', ondelete='cascade', index='btree_not_null')
    name = fields.Char("Period", required=True, readonly=True)
    date_from = fields.Date("From", required=True, readonly=True, index=True)
    date_to = fields.Date("To", required=True, readonly=True, index=True)
    payment_date = fields.Date(compute='_compute_payment_date', store=True, readonly=False, index=True)
    amount = fields.Monetary("Target", default=0, required=True, currency_field='currency_id')
    payment_amount = fields.Monetary(compute='_compute_payment_amount', currency_field='currency_id', store=True,
                                     help="Sum of amounts paid on the same payment date")
    currency_id = fields.Many2one('res.currency', related='plan_id.currency_id')
    target_type = fields.Selection(related='plan_id.target_type')

    @api.constrains('plan_id', 'date_from', 'date_to')
    def _constrains_overlapping_dates(self):
        targets_by_plans = self._read_group(
            domain=[('plan_id', 'in', self.plan_id.ids)],
            groupby=['plan_id'],
            aggregates=['id:recordset'],
        )
        for plan_id, target_ids in targets_by_plans:
            if len(target_ids) < 2:
                continue
            target_ids = target_ids.sorted(lambda t: (t.date_from, t.date_to))
            for idx in range(len(target_ids) - 1):
                current = target_ids[idx]
                next_one = target_ids[idx + 1]
                if current.date_from >= current.date_to:
                    raise ValidationError(self.env._(
                        "The start date must be before the end date.\nPeriod: %s"
                    ) % current.name)
                # Overlap detection: sorting can be indeterministic when the same date_from is used
                if current.date_to >= next_one.date_from:
                    raise ValidationError(self.env._(
                        "Overlapping periods detected for plan '%(plan)s':\n"
                        "- %(c_name)s [%(c_from)s → %(c_to)s]\n"
                        "- %(n_name)s [%(n_from)s → %(n_to)s]",
                        plan=plan_id.display_name,
                        c_name=current.name,
                        c_from=current.date_from,
                        c_to=current.date_to,
                        n_name=next_one.name,
                        n_from=next_one.date_from,
                        n_to=next_one.date_to,
                    ))

    @api.depends('date_to')
    def _compute_payment_date(self):
        for target in self:
            if not target.payment_date:
                target.payment_date = target.date_to

    @api.depends('payment_date', 'amount', 'plan_id')
    def _compute_payment_amount(self):
        """ Recompute the sum of amounts of the records sharing the same payment_date
        """
        amount_per_payment_date = defaultdict(list)
        total_per_date = defaultdict(float)
        # We need to group all related targets
        for target in self.plan_id.target_ids:
            # plan_id is used to avoid mixing targets from different plans
            key = (target.plan_id, target.payment_date)
            amount_per_payment_date[key].append(target.id)
            total_per_date[key] += target.amount
        for keys, target_ids in amount_per_payment_date.items():
            targets = self.browse(target_ids)
            targets.payment_amount = total_per_date[keys]
