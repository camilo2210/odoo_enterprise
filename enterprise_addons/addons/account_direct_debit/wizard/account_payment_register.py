from odoo import fields, models, api
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    needs_mandate_of_type = fields.Char(compute='_compute_needs_mandate_of_type')

    @api.depends('payment_type', 'payment_method_code')
    def _compute_needs_mandate_of_type(self):
        mandate_per_code = self.env['account.payment.method']._get_mandate_type_per_code()
        for wizard in self:
            wizard.needs_mandate_of_type = wizard.payment_type == 'inbound' and mandate_per_code.get(wizard.payment_method_code)

    @api.depends('payment_date', 'partner_id', 'company_id', 'line_ids.partner_id', 'payment_method_code')
    def _compute_actionable_errors(self):
        super()._compute_actionable_errors()
        for wizard in self.filtered('needs_mandate_of_type'):
            invalid_partners = wizard._get_partners_with_invalid_mandates()
            wizard.actionable_errors = {
                **(wizard.actionable_errors or {}),
                **self.env['account.direct.debit.mandate']._get_mandate_availability_alerts(wizard.needs_mandate_of_type, invalid_partners),
            }

    def _get_partners_with_invalid_mandates(self):
        """ Helper to search all partners linked to the payment registration wizard
        that don't have a valid mandate, in their move's company.
        """
        self.ensure_one()
        moves_to_pay = self.line_ids.move_id
        Mandate = self.env['account.direct.debit.mandate']
        domain = Mandate._get_usable_mandate_domain(
            moves_to_pay.company_id,
            moves_to_pay.commercial_partner_id,
            self.payment_date,
            mandate_type=self.needs_mandate_of_type,
        )
        valid_company_partner_pairs = {
            (company.id, partner.id)
            for company, partner in Mandate._read_group(domain, groupby=['company_id', 'partner_id'])
        }
        return moves_to_pay.filtered(
            lambda move: (move.company_id.id, move.commercial_partner_id.id) not in valid_company_partner_pairs
        ).commercial_partner_id

    def action_create_payments(self):
        for wizard in self.filtered('needs_mandate_of_type'):
            if invalid_partners := self._get_partners_with_invalid_mandates():
                # Avoid re-computation of fields that depend on line_ids or sub compute triggered by line_ids
                with self.env.protecting([self._fields['line_ids']], wizard):
                    wizard.line_ids = wizard.line_ids.filtered(lambda line: line.partner_id.commercial_partner_id not in invalid_partners)
                if not wizard.line_ids:
                    raise UserError(self.env._(
                        "You can't pay any of the selected invoices using direct debit, as no valid mandate is available."
                    ))

        return super().action_create_payments()
