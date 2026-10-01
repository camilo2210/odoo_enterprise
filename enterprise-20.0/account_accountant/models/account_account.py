import ast
from odoo import models, fields


class AccountAccount(models.Model):
    _inherit = "account.account"

    is_deferred = fields.Boolean(string="Deferred", tracking=True, help="Check to enable deferred accounting, deferred dates will be required on invoice / bill")
    deferred_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Deferred Account",
        copy=False,
        check_company=True,
        tracking=True,
        help="Account automatically used for deferred entries on this account.",
    )

    def action_open_reconcile(self):
        self.ensure_one()
        # Open reconciliation view for this account
        action_values = self.env['ir.actions.act_window']._for_xml_id('account_accountant.action_move_line_posted_unreconciled')
        domain = ast.literal_eval(action_values['domain'])
        domain.append(('account_id', '=', self.id))
        action_values['domain'] = domain
        return action_values
