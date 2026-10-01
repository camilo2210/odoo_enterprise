# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ph(self, companies):
        accounts_payable_other = 'l10n_ph_account_201020'
        sss_premiums_payable = 'l10n_ph_account_204010'
        philhealth_premiums_payable = 'l10n_ph_account_204020'
        hdmf_premiums_payable = 'l10n_ph_account_204030'
        net_pay_clearing = 'l10n_ph_account_205030'
        salaries_payable = 'l10n_ph_account_205040'
        withholding_tax_compensation = 'l10n_ph_account_206030'
        accrued_fringe_benefit_tax = 'l10n_ph_account_206050'
        other_bonuses_allowances = 'l10n_ph_account_601070'
        sss_contributions_expense = 'l10n_ph_account_601210'
        philhealth_contributions_expense = 'l10n_ph_account_601220'
        hdmf_contributions_expense = 'l10n_ph_account_601230'
        other_personnel_benefits = 'l10n_ph_account_601280'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           PH Employee Payroll Structure          #
        # ================================================ #

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_cash_fringe_benefits_rule')
        rules_mapping[rule]['debit'] = other_bonuses_allowances

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_non_cash_fringe_benefits_rule')
        rules_mapping[rule].update({
            'debit': other_personnel_benefits,
            'credit': net_pay_clearing,
        })

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_sss_contribution_rule')
        rules_mapping[rule]['debit'] = sss_premiums_payable

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_philhealth_contribution_rule')
        rules_mapping[rule]['debit'] = philhealth_premiums_payable

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_pag_ibig_contribution_rule')
        rules_mapping[rule]['debit'] = hdmf_premiums_payable

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_tax_rule')
        rules_mapping[rule]['debit'] = withholding_tax_compensation

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_tax_annualization_rule')
        rules_mapping[rule]['debit'] = withholding_tax_compensation

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_net_rule')
        rules_mapping[rule]['credit'] = salaries_payable

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_er_sss_contribution_rule')
        rules_mapping[rule].update({
            'debit': sss_contributions_expense,
            'credit': sss_premiums_payable,
        })

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_er_philhealth_contribution_rule')
        rules_mapping[rule].update({
            'debit': philhealth_contributions_expense,
            'credit': philhealth_premiums_payable,
        })

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_pag_er_ibig_contribution_rule')
        rules_mapping[rule].update({
            'debit': hdmf_contributions_expense,
            'credit': hdmf_premiums_payable,
        })

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_fbt_rule')
        rules_mapping[rule].update({
            'debit': other_bonuses_allowances,
            'credit': accrued_fringe_benefit_tax,
        })

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_ec_sss_contribution_rule')
        rules_mapping[rule].update({
            'debit': sss_contributions_expense,
            'credit': sss_premiums_payable,
        })

        rule = self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_expense_refund_pay_rule')
        rules_mapping[rule].update({
            'debit': accounts_payable_other,
            'credit': salaries_payable,
        })

        self._configure_payroll_account(
            companies,
            "PH",
            account_refs=[
                accounts_payable_other, sss_premiums_payable, philhealth_premiums_payable, hdmf_premiums_payable,
                net_pay_clearing, salaries_payable, withholding_tax_compensation, accrued_fringe_benefit_tax,
                other_bonuses_allowances, sss_contributions_expense, philhealth_contributions_expense,
                hdmf_contributions_expense, other_personnel_benefits,
            ],
            rules_mapping=rules_mapping,
            default_account=salaries_payable,
        )
