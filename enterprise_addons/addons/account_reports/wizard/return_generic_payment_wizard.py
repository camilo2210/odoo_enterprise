from odoo import api, models, fields


class AccountReturnGenericPaymentWizard(models.TransientModel):
    _name = "account.return.payment.wizard"
    _description = "Returns Generic Payment Wizard"

    company_id = fields.Many2one(comodel_name='res.company', string="Company")
    partner_id = fields.Many2one(comodel_name='res.partner', related='partner_bank_id.partner_id')
    account_number = fields.Char(string="IBAN", related='partner_bank_id.account_number')
    partner_bank_id = fields.Many2one(comodel_name='res.partner.bank')
    communication = fields.Char(compute='_compute_communication')

    show_vat_balance = fields.Boolean(compute="_compute_show_vat_balance")
    amount_to_pay = fields.Monetary(compute='_compute_amount_to_pay', store=True)
    vat_balance = fields.Monetary(compute='_compute_vat_balance')
    is_recovered = fields.Boolean(string="Does this payment recover previous recoverable amounts")
    is_recoverable = fields.Boolean(compute='_compute_is_recoverable', readonly=False)
    currency_id = fields.Many2one(comodel_name='res.currency', related='return_id.amount_to_pay_currency_id')
    return_id = fields.Many2one(comodel_name='account.return', required=True)

    def _generate_communication(self):
        return False

    @api.depends('vat_balance', 'amount_to_pay', 'currency_id')
    def _compute_show_vat_balance(self):
        for wizard in self:
            wizard.show_vat_balance = wizard.currency_id.compare_amounts(wizard.amount_to_pay, wizard.vat_balance) != 0

    @api.depends('return_id')
    def _compute_amount_to_pay(self):
        for wizard in self:
            wizard.amount_to_pay = wizard.return_id.period_amount_to_pay

    @api.depends('return_id')
    def _compute_vat_balance(self):
        for wizard in self:
            receivable_account = wizard.return_id._get_tax_closing_payable_and_receivable_accounts()[1]
            wizard.vat_balance = wizard.return_id._evaluate_total_amount_to_pay_from_tax_closing_accounts(receivable_account)

    @api.depends('amount_to_pay')
    def _compute_is_recoverable(self):
        for wizard in self:
            result = wizard.currency_id.compare_amounts(wizard.amount_to_pay, 0)
            wizard.is_recoverable = result == -1 or result == 0

    @api.depends('company_id')
    def _compute_communication(self):
        for wizard in self:
            wizard.communication = wizard._generate_communication()

    def action_mark_as_paid(self):
        self.ensure_one()
        if self.is_recovered:
            payable_accounts, receivable_accounts = self.return_id._get_tax_closing_payable_and_receivable_accounts()

            receivable_lines_by_company = dict(
                self.env['account.move.line']._read_group(
                    [
                        ('date', '<=', self.return_id.date_to),
                        ('account_id', 'in', receivable_accounts.ids),
                        ('company_id', 'in', self.return_id.company_ids.ids),
                        ('move_id.state', '=', 'posted'),
                        ('reconciled', '=', False),
                    ],
                    groupby=['company_id'],
                    aggregates=['id:recordset'],
                )
            )

            for closing_entry in self.return_id.closing_move_ids:
                company = closing_entry.company_id
                if company in receivable_lines_by_company:
                    receivable_lines_to_reconcile = receivable_lines_by_company[company]
                    payable_lines = closing_entry.line_ids.filtered(lambda line: line.account_id.id in payable_accounts.ids)
                    wizard = self.env['account.reconcile.wizard'].with_context(
                        active_model='account.move.line',
                        active_ids=[*receivable_lines_to_reconcile.ids, *payable_lines.ids],
                    ).new({})
                    wizard.allow_partials = True
                    wizard.reconcile()

            # Re assign the most recent computes value to ensure it stays coherent
            self.return_id.total_amount_to_pay = self.vat_balance

        return self.return_id._action_finalize_payment()

    def action_send_email_instructions(self):
        self.ensure_one()
        template = self.env.ref('account_reports.email_template_generic_tax_instructions', raise_if_not_found=False)
        return self.return_id.action_send_email_instructions(self, template)

    def action_deduct_receivable_amount(self):
        self.ensure_one()
        if not self.show_vat_balance:
            return
        self.is_recovered = True
        self.amount_to_pay = max(self.vat_balance, 0)
