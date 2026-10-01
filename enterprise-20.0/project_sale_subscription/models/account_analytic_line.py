from odoo import api, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    def _get_billable_types(self):
        return super()._get_billable_types() + [(50, '17_subscriptions', self.env._('Subscriptions'))]

    @api.depends('product_id.recurring_invoice', 'so_line.product_id.recurring_invoice')
    def _compute_project_billable_type(self):
        super()._compute_project_billable_type()

    @api.depends('billable_type')
    def _compute_category_report(self):
        subscriptions = self.filtered(lambda aal: aal.billable_type == '17_subscriptions')
        subscriptions.category_report = 'revenues'
        super(AccountAnalyticLine, self - subscriptions)._compute_category_report()

    def _get_invoice_type(self, invoice_type):
        if self._get_billable_product().recurring_invoice:
            return '17_subscriptions'
        return super()._get_invoice_type(invoice_type)
