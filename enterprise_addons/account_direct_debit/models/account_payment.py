from odoo import models, fields, api
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import format_date


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    needs_mandate_of_type = fields.Char(compute='_compute_needs_mandate_of_type')
    mandate_id = fields.Many2one(
        comodel_name='account.direct.debit.mandate',
        string="Mandate",
        copy=False,
        check_company=True,
        compute='_compute_mandate_id',
        store=True,
        readonly=False,
        domain="[('state', '=', 'active'), ('partner_id', '=', commercial_partner_id), ('mandate_type', '=', needs_mandate_of_type)]",
        index='btree_not_null',
        help="Once this invoice has been paid with Direct Debit, contains the mandate that allowed the payment.",
    )

    @api.constrains('partner_id', 'mandate_id', 'date', 'payment_method_id')
    def _validate_mandate_id(self):
        for payment in self.filtered(lambda p: p.needs_mandate_of_type or p.mandate_id):
            mandate = payment.mandate_id
            if payment.state != 'draft' and not mandate:
                raise ValidationError(self.env._(
                    "This %(payment_method)s payment needs a mandate.",
                    payment_method=payment.payment_method_id.display_name,
                ))
            if not mandate:
                continue
            if mandate.partner_id != payment.commercial_partner_id:
                raise ValidationError(self.env._("Trying to register a payment on a mandate belonging to a different partner."))
            if mandate.mandate_type != payment.needs_mandate_of_type:
                raise ValidationError(self.env._(
                    "The mandate %(mandate)s cannot be used to collect a %(payment_method)s payment.",
                    mandate=mandate.display_name,
                    payment_method=payment.payment_method_id.display_name,
                ))
            if payment.date < mandate.start_date or (mandate.end_date and mandate.end_date < payment.date):
                raise ValidationError(self.env._(
                    "The mandate %(mandate)s is not valid on %(date)s.",
                    mandate=mandate.display_name,
                    date=format_date(self.env, payment.date),
                ))

    @api.constrains('mandate_id', 'return_partner_bank_id')
    def _validate_mandate_bank_account(self):
        for payment in self.filtered('mandate_id'):
            if payment.return_partner_bank_id != payment.mandate_id.partner_bank_id:
                raise ValidationError(self.env._(
                    "The bank account to collect from must be the one authorized by the mandate %(mandate)s.",
                    mandate=payment.mandate_id.display_name,
                ))

    @api.onchange('commercial_partner_id')
    def _onchange_partner_id(self):
        mandate_per_code = self.env['account.payment.method']._get_mandate_type_per_code()
        for payment in self:
            if payment.payment_type != 'inbound' or not payment.commercial_partner_id:
                continue
            # Any mandate scheme: the mandate found is what decides the payment method selected below
            mandate = self.env['account.direct.debit.mandate']._get_usable_mandate(
                payment.company_id.id or self.env.company.id,
                payment.commercial_partner_id.id,
                payment.date,
            )
            if (
                mandate
                and (matching_pm_line := payment.available_payment_method_line_ids.filtered(lambda l:
                    mandate_per_code.get(l.code) == mandate.mandate_type
                ))
            ):
                payment.payment_method_line_id = matching_pm_line[0]
                payment.mandate_id = mandate

    @api.depends('payment_type', 'payment_method_line_id')
    def _compute_needs_mandate_of_type(self):
        mandate_per_code = self.env['account.payment.method']._get_mandate_type_per_code()
        for payment in self:
            payment.needs_mandate_of_type = payment.payment_type == 'inbound' and mandate_per_code.get(payment.payment_method_line_id.code)

    @api.depends('needs_mandate_of_type', 'partner_id', 'date')
    def _compute_mandate_id(self):
        for payment in self:
            payment.mandate_id = payment.state == 'draft' and payment.needs_mandate_of_type and payment._get_usable_mandate()

    @api.depends('mandate_id')
    def _compute_return_partner_bank_id(self):
        super()._compute_return_partner_bank_id()
        for payment in self.filtered('mandate_id'):
            payment.return_partner_bank_id = payment.mandate_id.partner_bank_id

    @api.depends('payment_type', 'payment_method_id', 'partner_id', 'mandate_id', 'state', 'date')
    def _compute_alerts(self):
        super()._compute_alerts()
        for payment in self.filtered(lambda p: p.state == 'draft' and p.needs_mandate_of_type):
            partner_without_mandate = payment.commercial_partner_id if not payment.mandate_id else self.env['res.partner']
            payment.alerts = {
                **(payment.alerts or {}),
                **self.env['account.direct.debit.mandate']._get_mandate_availability_alerts(payment.needs_mandate_of_type, partner_without_mandate),
            }

    def _get_usable_mandate(self):
        """ Returns the direct debit mandate that can be used to generate this payment. """
        self.ensure_one()
        if not self.needs_mandate_of_type:
            return self.env['account.direct.debit.mandate']
        return self.env['account.direct.debit.mandate']._get_usable_mandate(
            self.company_id or self.env.company,
            self.commercial_partner_id,
            self.date,
            mandate_type=self.needs_mandate_of_type,
        )

    def _filter_needs_mandate_but_invalid(self):
        # Also closes the mandates that have expired
        mandates_by_validity = self.mandate_id._update_and_partition_state_by_validity()
        invalid_mandates = mandates_by_validity.get('invalid', self.env['account.direct.debit.mandate'])
        return self.filtered(lambda p: p.needs_mandate_of_type and p.mandate_id in invalid_mandates)

    def action_post(self):
        self.mandate_id._update_and_partition_state_by_validity()
        for payment in self.filtered(lambda p: p.state == 'draft' and p.needs_mandate_of_type):
            if not payment.mandate_id and payment._get_usable_mandate():
                raise UserError(self.env._(
                    "Select the mandate to collect this payment with before confirming it."
                ))
            if payment.mandate_id and payment.mandate_id.state != 'active':
                raise UserError(self.env._(
                    "The selected mandate is not active, this payment cannot be confirmed."
                ))
            if not payment.mandate_id:
                partner = payment.commercial_partner_id
                raise RedirectWarning(
                    self.env._(
                        "No valid mandate for %(partner)s, this payment cannot be confirmed.",
                        partner=partner.display_name,
                    ),
                    action=partner.action_open_mandates(),
                    button_text=self.env._("Create it."),
                )
        return super().action_post()

    def write(self, vals):
        was_not_paid = self.filtered(lambda p: p.state not in ('in_payment', 'paid'))
        result = super().write(vals)
        if mandates_to_close := was_not_paid.filtered(lambda p:
            p.state in ('in_payment', 'paid') and p.mandate_id.one_off
        ).mandate_id:
            mandates_to_close.sudo().action_close_mandate()
        return result
