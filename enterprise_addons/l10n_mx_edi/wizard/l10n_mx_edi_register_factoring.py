from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError


class L10n_Mx_Edi_RegisterFactoring(models.TransientModel):
    _name = 'l10n_mx_edi.register.factoring'
    _description = 'Register factoring payment'

    statement_line_id = fields.Many2one(
        comodel_name='account.bank.statement.line',
        required=True,
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one(related='statement_line_id.company_id')
    transaction_currency_id = fields.Many2one(comodel_name='res.currency', compute="_compute_transaction_currency_id")
    company_currency_id = fields.Many2one(related="company_id.currency_id")
    move_line_ids = fields.Many2many(
        comodel_name='account.move.line',
        check_company=True,
        required=True,
        ondelete='cascade'
    )
    line_ids = fields.One2many(
        comodel_name='l10n_mx_edi.register.factoring.line',
        inverse_name='wizard_id',
        compute='_compute_line_ids',
        store=True, readonly=False,
        check_company=True,
    )

    # Due in transaction currency
    amount_residual_currency = fields.Monetary(compute="_compute_amounts_residual", currency_field="transaction_currency_id")
    # Due in company currency
    amount_residual = fields.Monetary(compute="_compute_amounts_residual", string='Amount Due', currency_field="company_currency_id")

    @api.depends('statement_line_id.currency_id', 'statement_line_id.foreign_currency_id')
    def _compute_transaction_currency_id(self):
        for wizard in self:
            st_line = wizard.statement_line_id
            wizard.transaction_currency_id = st_line.foreign_currency_id or st_line.currency_id

    @api.depends(
        'statement_line_id',
        'line_ids.amount',
        'line_ids.amount_trans_currency',
    )
    def _compute_amounts_residual(self):
        for wizard in self:
            transaction_amount_residual, company_amount_residual = wizard.statement_line_id._get_statement_line_residual_amounts()

            total_paid = sum(wizard.line_ids.mapped('amount'))
            total_paid_currency = sum(wizard.line_ids.mapped('amount_trans_currency'))

            wizard.amount_residual = -company_amount_residual - total_paid
            wizard.amount_residual_currency = -transaction_amount_residual - total_paid_currency

    @api.depends('move_line_ids')
    def _compute_line_ids(self):
        for wizard in self:
            wizard.line_ids = [
                Command.create({'move_line_id': inv_line.id})
                for inv_line in wizard.move_line_ids
            ]

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)

        statement_line = self.env['account.bank.statement.line'].browse(self.env.context.get('statement_line_id', []))
        if not statement_line.partner_id:
            raise ValidationError(_('To register a factoring payment, you first need to set the factor contact in the payment.'))
        if not statement_line.l10n_mx_edi_can_use_factoring:
            raise ValidationError(_('You cannot use factoring on this document'))

        move_lines = self.env['account.move.line'].browse(self.env.context.get('move_line_ids', []))
        moves = move_lines.move_id
        all_invoices = all(move._l10n_mx_edi_is_cfdi_document() and move.move_type == 'out_invoice' and move.state == 'posted' for move in moves)
        if not move_lines or not all_invoices:
            raise ValidationError(_('Factoring is only allowed for posted customer invoices.'))
        if len(moves.company_id.ids) > 1:
            raise ValidationError(_('All invoices must be from the same company.'))
        if any(line.account_type != 'asset_receivable' or line.reconciled for line in move_lines):
            raise ValidationError(_("Some invoice lines don't have any remaing amount to be paid"))

        result['move_line_ids'] = [Command.set(move_lines.ids)]
        result['statement_line_id'] = statement_line.id
        return result

    def action_apply_factoring(self):
        """Register the amounts for each factoring payment by creating the respective lines at the statement."""
        self.ensure_one()
        for line in self.line_ids:
            if line.has_invalid_amount:
                raise UserError(_("You have paid more than what is due for some journal items."))
            if line.transaction_currency_id.is_zero(line.amount_trans_currency):
                raise UserError(_("You can't apply a factoring payment with a line with zero amount."))

        factoring_account_id = self.company_id.l10n_mx_edi_factoring_account_id.id
        if not factoring_account_id:
            raise ValidationError(_("There is not a default factoring account set in your company."))

        amls_to_create = []
        for line in self.line_ids:
            amls_to_create.append(line._get_aml_values())

            if line.compensation_amount:
                compensation_line_vals = line._get_aml_values(is_compensation=True)

                factoring_cost_line_vals = {
                    **compensation_line_vals,
                    'balance': line.compensation_amount,
                    'amount_currency': line.compensation_amount_trans_currency,
                    'reconciled_lines_ids': False,
                    'l10n_mx_edi_factoring_type': 'factoring_cost',
                    'account_id': factoring_account_id,
                    'partner_id': self.statement_line_id.partner_id.id,
                }

                amls_to_create.extend([compensation_line_vals, factoring_cost_line_vals])

        if amls_to_create:
            self.statement_line_id._add_move_line_to_statement_line_move(amls_to_create)

        return True


class L10n_Mx_Edi_RegisterFactoringLine(models.TransientModel):
    _name = 'l10n_mx_edi.register.factoring.line'
    _description = 'Register factoring amounts by line'

    wizard_id = fields.Many2one(
        comodel_name='l10n_mx_edi.register.factoring',
        required=True,
        ondelete='cascade',
        check_company=True,
    )
    company_id = fields.Many2one(related="wizard_id.company_id")
    statement_line_id = fields.Many2one(related="wizard_id.statement_line_id", check_company=True)
    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        required=True,
        ondelete='cascade',
        check_company=True,
    )
    partner_id = fields.Many2one(related='move_line_id.partner_id', check_company=True)
    transaction_currency_id = fields.Many2one(related="wizard_id.transaction_currency_id")
    move_line_currency_id = fields.Many2one(related='move_line_id.currency_id', string="Move Line Currency")
    company_currency_id = fields.Many2one(related='wizard_id.company_currency_id', string="Company Currency")

    # Amounts in transaction currency
    amount_trans_currency = fields.Monetary(
        string='To Pay',
        currency_field="transaction_currency_id",
    )
    compensation_amount_trans_currency = fields.Monetary(
        string='Compensation',
        currency_field="transaction_currency_id",
    )

    # Amounts in company currency
    amount = fields.Monetary(
        compute='_compute_amount',
        currency_field='company_currency_id',
        store=True, readonly=False,
    )
    compensation_amount = fields.Monetary(
        compute='_compute_compensation_amount',
        currency_field='company_currency_id',
        store=True, readonly=False,
    )

    # Invoice amounts in its and company currency
    amount_residual_currency = fields.Monetary(related='move_line_id.amount_residual_currency', currency_field='move_line_currency_id')
    amount_residual = fields.Monetary(related="move_line_id.amount_residual", currency_field='company_currency_id')

    has_invalid_amount = fields.Boolean(compute='_compute_has_invalid_amount')

    @api.depends('amount_trans_currency')
    def _compute_amount(self):
        for line in self:
            line.amount = line._convert_to_company_currency(line.amount_trans_currency)

    @api.depends('compensation_amount_trans_currency')
    def _compute_compensation_amount(self):
        for line in self:
            line.compensation_amount = line._convert_to_company_currency(line.compensation_amount_trans_currency)

    @api.depends('move_line_id')
    def _compute_display_name(self):
        for line in self:
            inv_line = line.move_line_id
            line.display_name = f'{inv_line.move_id.name} - {inv_line.name}'

    @api.depends('amount_trans_currency', 'compensation_amount_trans_currency')
    def _compute_has_invalid_amount(self):
        for line in self:
            amount_paid_line_currency, compensation_line_currency = line._get_amounts_in_line_currency()
            total_paid = amount_paid_line_currency + compensation_line_currency
            line.has_invalid_amount = (
                line.move_line_currency_id.compare_amounts(total_paid, line.amount_residual_currency) > 0
                or line.move_line_currency_id.compare_amounts(total_paid, 0) < 0
            )

    def _convert_to_company_currency(self, amount_currency):
        """Convert the given amount to its equivalent on company currency using the statement line rate

            :param amount_currency:      Amount in the transaction currency
            :returns:                    The amount in the company currency
        """
        self.ensure_one()

        amount_in_company_curr = self.transaction_currency_id._convert(
            from_amount=amount_currency,
            to_currency=self.company_currency_id,
            company=self.wizard_id.company_id,
            date=self.wizard_id.statement_line_id.date
        )

        # Convert company amount to st_line rate
        return self.wizard_id.statement_line_id._prepare_counterpart_amounts_using_st_line_rate(
            self.transaction_currency_id,
            amount_in_company_curr,
            amount_currency
        )['balance']

    def _get_aml_values(self, is_compensation=False):
        return {
            'account_id': self.move_line_id.account_id.id,
            'balance': -self.amount if not is_compensation else -self.compensation_amount,
            'amount_currency': -self.amount_trans_currency if not is_compensation else -self.compensation_amount_trans_currency,
            'currency_id': self.transaction_currency_id.id,
            'reconciled_lines_ids': [Command.set(self.move_line_id.ids)],
            'name': self.display_name if not is_compensation else _('Factoring'),
            'partner_id': self.partner_id.id,
            'l10n_mx_edi_factoring_type': is_compensation and 'compensation',
        }

    def _get_amounts_in_line_currency(self):
        """Returns line amount and compensation after converting them to the invoice currency"""
        self.ensure_one()
        move_line = self.move_line_id

        if move_line.currency_id == self.transaction_currency_id:
            return self.amount_trans_currency, self.compensation_amount_trans_currency

        if move_line.currency_id == self.company_currency_id:
            return self.amount, self.compensation_amount

        # Compute the difference between the balance of the invoice with the balance of the transaction rate
        exchange_diff = self.statement_line_id._lines_get_account_balance_exchange_diff(move_line.currency_id, move_line.balance, move_line.amount_currency)
        amount_total_company_currency = move_line.balance + exchange_diff

        rate_company2move_currency = abs(move_line.balance / amount_total_company_currency) if amount_total_company_currency else 0.0

        amount_paid_move_currency = move_line.currency_id.round(self.amount * rate_company2move_currency)
        compensation_move_currency = move_line.currency_id.round(self.compensation_amount * rate_company2move_currency)

        return amount_paid_move_currency, compensation_move_currency
