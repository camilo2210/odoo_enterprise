from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.l10n_ca_payment_cpa005.models.res_partner_bank import (
    cpa005_sanitize_account_number,
    cpa005_sanitize_financial_institution_nr,
)

# CPA Rules H1 require the payor to be notified at least 10 days before a PAD collection.
CPA005_MIN_PRENOT_PERIOD = 10


class AccountDirectDebitMandate(models.Model):
    """ CPA 005 Pre-Authorized Debit (PAD) extension of the generic mandate. """
    _inherit = 'account.direct.debit.mandate'

    mandate_type = fields.Selection(
        selection_add=[
            ('cpa005_pad', 'CPA005 PAD'),
        ],
        ondelete={'cpa005_pad': 'cascade'},
    )
    l10n_ca_cpa005_pad_category = fields.Selection(
        selection=[
            ('personal', "Personal (Utilities, Mortgage, ...)"),
            ('business', "Business (Commercial Activities)"),
        ],
        string="PAD Category",
        help="Payments Canada PAD category, printed on the PAD agreement.",
    )

    @api.constrains('mandate_type', 'l10n_ca_cpa005_pad_category')
    def _l10n_ca_cpa005_validate_pad_category(self):
        if self.filtered(lambda m: m.mandate_type == 'cpa005_pad' and not m.l10n_ca_cpa005_pad_category):
            raise ValidationError(self.env._("A CPA 005 PAD mandate requires a PAD category."))

    def _compute_mandate_type(self):
        ca_mandates = self.filtered(lambda m: m.country_code == 'CA' and not m.mandate_type)
        ca_mandates.mandate_type = 'cpa005_pad'
        super(AccountDirectDebitMandate, self - ca_mandates)._compute_mandate_type()

    def _get_min_pre_notification_period(self):
        if self.mandate_type == 'cpa005_pad':
            return CPA005_MIN_PRENOT_PERIOD
        return super()._get_min_pre_notification_period()

    def _check_bank_account_for_validation(self):
        super()._check_bank_account_for_validation()
        for mandate in self.filtered(lambda m: m.mandate_type == 'cpa005_pad'):
            if not mandate.partner_bank_id:
                raise UserError(self.env._("A CPA 005 PAD mandate requires a customer bank account."))
            elif not cpa005_sanitize_account_number(mandate.partner_bank_id.account_number):
                raise UserError(self.env._("A CPA 005 PAD mandate requires a valid bank account number."))
            if not mandate.partner_bank_id.l10n_ca_financial_institution_number:
                raise UserError(self.env._("A CPA 005 PAD mandate requires a customer bank account with a Financial Institution ID Number."))
            elif not cpa005_sanitize_financial_institution_nr(mandate.partner_bank_id.l10n_ca_financial_institution_number):
                raise UserError(self.env._("A CPA 005 PAD mandate requires a customer bank account with a valid Financial Institution ID Number."))

    def _get_report_template(self):
        if self.mandate_type == 'cpa005_pad':
            return 'l10n_ca_payment_cpa005.cpa005_pad_mandate_form'
        return super()._get_report_template()

    def _get_send_mail_template(self):
        if self.mandate_type == 'cpa005_pad':
            return self.env.ref('l10n_ca_payment_cpa005.email_template_cpa005_pad_mandate', raise_if_not_found=False)
        return super()._get_send_mail_template()
