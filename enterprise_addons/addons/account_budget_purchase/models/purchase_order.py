from odoo import fields, models, api


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    is_above_budget = fields.Boolean('Is Above Budget', compute='_compute_above_budget', compute_sudo=True)
    is_analytic = fields.Boolean('Is Analytic', compute='_compute_is_analytic')

    @api.depends('order_line.analytic_distribution')
    def _compute_is_analytic(self):
        for order in self:
            order.is_analytic = any(order.order_line.mapped('analytic_distribution'))

    @api.depends(
        'order_line.budget_line_ids',
        'order_line.non_deductible_tax',
        'order_line.price_unit',
        'order_line.product_qty',
        'order_line.qty_invoiced',
        'state',
    )
    def _compute_above_budget(self):
        for order in self:
            uncommitted_amount = 0.0
            if order.state not in ('purchase', 'done'):
                for line in order.order_line.filtered(lambda l: l.budget_line_ids):
                    uncommitted_qty = (line.product_qty - line.qty_invoiced)
                    uncommitted_amount += line.price_unit * uncommitted_qty
                    uncommitted_amount += line.non_deductible_tax * uncommitted_qty / line.product_qty if line.product_qty else 0.0
            order.is_above_budget = any(
                budget.committed_amount + uncommitted_amount > budget.budget_amount
                for budget in order.order_line.mapped('budget_line_ids')
            )

    def action_budget(self):
        self.ensure_one()
        analytic_account_ids = [
            int(account)
            for line in self.order_line
            for account_ids in (line.analytic_distribution or {})
            for account in account_ids.split(',')
        ]
        action = self.env["ir.actions.actions"]._for_xml_id("account_budget.budget_report_action")
        action['domain'] = [('auto_account_id', 'in', analytic_account_ids), ('budget_analytic_id.budget_type', '!=', 'revenue')]
        return action
