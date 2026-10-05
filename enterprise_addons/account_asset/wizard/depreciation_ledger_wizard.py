# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError


class DepreciationLedgerWizard(models.TransientModel):
    _name = 'depreciation.ledger.wizard'
    _description = 'Wizard used to apply depreciations models on ledger assets'

    asset_id = fields.Many2one(
        comodel_name='account.asset',
    )
    company_id = fields.Many2one(related='asset_id.company_id')
    ledger_group_ids = fields.Many2many(
        comodel_name='account.journal.group',
        compute='_compute_ledger_group_ids',
    )

    depreciation_model_id = fields.Many2one(
        comodel_name='account.depreciation.model',
        string='Depreciation Model',
        domain="[('journal_id.journal_group_id', '!=', False)]",
    )
    depreciation_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Accumulated Account",
        domain=[('account_type', 'in', ('asset_fixed', 'asset_non_current', 'equity'))],
        check_company=True,
        compute='_compute_accounts', store=True, readonly=False,
    )
    expense_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Expense Account",
        domain=[('account_type', 'in', ('expense_depreciation', 'expense_other', 'expense'))],
        check_company=True,
        compute='_compute_accounts', store=True, readonly=False,
    )
    recovery_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Recovery Account",
        domain=[('account_type', 'in', ('income', 'income_other'))],
        check_company=True,
        compute='_compute_accounts', store=True, readonly=False,
        help="Account used to record the reversal of excess depreciation when statutory depreciation catches up or the asset is disposed of.",
    )

    @api.depends('depreciation_model_id')
    def _compute_accounts(self):
        for wizard in self:
            model = wizard.depreciation_model_id
            # A model that names no accounts of its own posts where the asset already does.
            main_variant = wizard.asset_id.main_variant_id
            wizard.depreciation_account_id = model.ledger_depreciation_account_id or main_variant.account_depreciation_id
            wizard.expense_account_id = model.ledger_expense_account_id or main_variant.account_depreciation_expense_id
            wizard.recovery_account_id = model.ledger_recovery_account_id

    @api.depends('asset_id')
    def _compute_ledger_group_ids(self):
        for record in self:
            record.ledger_group_ids = record.asset_id.variant_ids.journal_id.journal_group_id

    def apply(self):
        if not self.depreciation_model_id:
            raise UserError(self.env._("Need to set depreciation model to create new asset depreciation."))
        variant = self.asset_id._create_variants(self.depreciation_model_id, variant_vals={
            'account_depreciation_id': self.depreciation_account_id.id,
            'account_depreciation_expense_id': self.expense_account_id.id,
            'recovery_account_id': self.recovery_account_id.id,
        })
        variant.validate()
        return {'type': 'ir.actions.act_window_close'}
