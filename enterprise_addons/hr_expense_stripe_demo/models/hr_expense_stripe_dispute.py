from odoo import api, models


class HrExpenseStripeDispute(models.Model):
    _inherit = 'hr.expense.stripe.dispute'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reason') == 'no_valid_authorization':
                vals['explanation'] = 'winning_evidence'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('reason') == 'no_valid_authorization':
            vals['explanation'] = 'winning_evidence'
        return super().write(vals)
