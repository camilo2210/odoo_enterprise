import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils

SDD_MIN_PRENOT_PERIOD = 2
SDD_FIRST_MIN_PRENOT_PERIOD = 5
SDD_INACTIVITY_EXPIRY_MONTHS = 36


class AccountDirectDebitMandate(models.Model):
    """ SEPA-specific extension of the generic direct debit mandate. """
    _inherit = 'account.direct.debit.mandate'

    mandate_type = fields.Selection(selection_add=[('sepa', 'SEPA')], ondelete={'sepa': 'cascade'})
    sdd_scheme = fields.Selection(
        string="SDD Scheme",
        selection=[('CORE', "CORE (For consumers, refund possible)"), ('B2B', "B2B (Business only, no refund)")],
        default='CORE',
        help="""
            - CORE: For consumers; allows refund within 8 weeks of the debit.
            - B2B: For business accounts only; no refund rights once executed.
            """,
    )
    sdd_debtor_id_code = fields.Char(
        string="SEPA Debtor Identifier",
        help="Free reference identifying the debtor in your company.",
    )

    @api.constrains('mandate_type', 'sdd_debtor_id_code')
    def _sepa_validate_debtor_id_code(self):
        if self.filtered(lambda mandate:
            mandate.mandate_type == 'sepa' and mandate.sdd_debtor_id_code and len(mandate.sdd_debtor_id_code) > 35
        ):
            # Arbitrary limitation given by SEPA regulation for the <id> element used for this field when generating the XML
            raise UserError(self.env._("The debtor identifier you specified exceeds the limitation of 35 characters imposed by SEPA regulation"))

    def _compute_mandate_type(self):
        sepa_country_codes = self.env.ref('base.sepa_zone').country_ids.mapped('code')
        sepa_mandates = self.filtered(lambda m: m.country_code in sepa_country_codes and not m.mandate_type)
        sepa_mandates.mandate_type = 'sepa'
        super(AccountDirectDebitMandate, self - sepa_mandates)._compute_mandate_type()

    def _check_bank_account_for_validation(self):
        super()._check_bank_account_for_validation()
        for mandate in self.filtered(lambda m: m.mandate_type == 'sepa'):
            if mandate.partner_bank_id.account_type != 'iban':
                raise UserError(self.env._("SEPA Direct Debit scheme only accepts IBAN account numbers."))

    def _ensure_required_data(self):
        super()._ensure_required_data()
        for mandate in self.filtered(lambda m: m.mandate_type == 'sepa'):
            if mandate.sdd_scheme == 'B2B' and not mandate.partner_id.is_company:
                raise UserError(self.env._("Under B2B SDD Scheme, the customer must be a company."))

    def _get_report_base_filename(self):
        if self.mandate_type == 'sepa':
            return re.sub(r'\W+', '_', self.env._(
                "%(partner_name)s_mandate_form_%(mandate_name)s",
                partner_name=self.partner_id.name,
                mandate_name=self.name,
            ))
        return super()._get_report_base_filename()

    def _get_inactivity_expiry_delay(self):
        if self.mandate_type == 'sepa':
            return date_utils.relativedelta(months=SDD_INACTIVITY_EXPIRY_MONTHS)
        return super()._get_inactivity_expiry_delay()

    def _get_report_template(self):
        if self.mandate_type == 'sepa':
            return 'account_sepa_direct_debit.sdd_mandate_form'
        return super()._get_report_template()

    def _get_send_mail_template(self):
        if self.mandate_type == 'sepa':
            return self.env.ref('account_sepa_direct_debit.email_template_sdd_new_mandate', raise_if_not_found=False)
        return super()._get_send_mail_template()

    def _get_expiry_mail_template(self):
        if self.mandate_type == 'sepa':
            return self.env.ref('account_sepa_direct_debit.email_template_sdd_mandate_expiring', raise_if_not_found=False)
        return super()._get_expiry_mail_template()
