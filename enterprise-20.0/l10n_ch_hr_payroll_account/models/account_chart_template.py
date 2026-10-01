# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ch(self, companies):
        salary_pass_through = 'ch_coa_1090'
        transfer_salaries = 'ch_coa_1091'
        health_insurance_ahv = 'ch_coa_2270'
        short_term_liabilities = 'ch_coa_2210'
        lpp_provision = 'ch_coa_2271'
        health_insurance_caf = 'ch_coa_2272'
        assurance_accident = 'ch_coa_2273'
        sickness_insurance = 'ch_coa_2274'
        source_tax = 'ch_coa_2279'
        provision_13th = 'ch_coa_2350'
        provision_14th = 'ch_coa_2351'
        wages = 'ch_coa_5000'
        social_insurance_payments = 'ch_coa_5001'
        profit_sharing = 'ch_coa_5002'
        month_13th = 'ch_coa_5005'
        bonus = 'ch_coa_5007'
        commissions = 'ch_coa_5010'
        month_14th = 'ch_coa_5011'
        ahv = 'ch_coa_5700'
        fak = 'ch_coa_5710'
        lpp = 'ch_coa_5720'
        aanp = 'ch_coa_5730'
        laac = 'ch_coa_5731'
        ijm = 'ch_coa_5740'
        is_tax = 'ch_coa_5790'
        other_expenses = 'ch_coa_5800'
        prof_training = 'ch_coa_5810'
        travel_expenses = 'ch_coa_5820'
        representation_fees = 'ch_coa_5830'
        fixed_rate_expenses = 'ch_coa_5832'
        rate_personal_use = 'ch_coa_5890'
        comp_company_car = 'ch_coa_5891'
        vehicle_expenses = 'ch_coa_6200'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           CH Employee Payroll Structure          #
        # ================================================ #

        rules_with_default_mapping = [
            "1000", "1001", "1005", "1006", "1065", "1061", "1067", "1160", "1161", "1015", "1016", "1017",
            "1018", "1020", "1021", "1031", "1032", "1033", "1034", "1040", "1050", "1055", "1056", "1060",
            "1070", "1071", "1072", "1074", "1076", "1100", "1101", "1102", "1103", "1104", "1110", "1111",
            "1131", "1162", "1163", "1230", "1231", "1299", "1300", "1301", "1302", "1303", "1304", "1305",
            "1306", "1307", "1500", "1501", "1503", "1953", "1955", "1973", "2025", "2026", "2027", "2030",
            "2031", "2032", "2035", "2040", "2070", "4900", "1207", "1208"
        ]

        bonuses = [
            "1010", "1030", "1073", "1075", "1112", "1130", "1202", "1204", "1209", "1210", "1212", "1213",
            "1214", "1215", "1216", "1217", "1219", "1232", "1250", "3032"
        ]

        bonus_rules = self.env['hr.salary.rule'].search([('l10n_ch_code', 'in', bonuses), ('struct_ids', 'in', self.env.ref('l10n_ch_hr_payroll.hr_payroll_structure_ch_elm').id)])
        for rule in bonus_rules:
            rules_mapping[rule]['debit'] = bonus
            rules_mapping[rule]['credit'] = salary_pass_through

        wage_rules = self.env['hr.salary.rule'].search([('l10n_ch_code', 'in', rules_with_default_mapping), ('struct_ids', 'in', self.env.ref('l10n_ch_hr_payroll.hr_payroll_structure_ch_elm').id)])
        for rule in wage_rules:
            rules_mapping[rule]['debit'] = wages
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_1510', 'l10n_ch_elm_1218']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = profit_sharing
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1211')
        rules_mapping[rule]['debit'] = commissions
        rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_1400', 'l10n_ch_elm_1401', 'l10n_ch_elm_1410', 'l10n_ch_elm_1411', 'l10n_ch_elm_1420']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = transfer_salaries
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_1900', 'l10n_ch_elm_1901', 'l10n_ch_elm_1902']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = rate_personal_use
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1910')
        rules_mapping[rule]['debit'] = salary_pass_through
        rules_mapping[rule]['credit'] = vehicle_expenses

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1950')
        rules_mapping[rule]['debit'] = rate_personal_use
        rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_1960', 'l10n_ch_elm_1961', 'l10n_ch_elm_1962']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = transfer_salaries
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1971')
        rules_mapping[rule]['debit'] = ijm
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1972')
        rules_mapping[rule]['debit'] = lpp
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1974')
        rules_mapping[rule]['debit'] = ijm
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1975')
        rules_mapping[rule]['debit'] = aanp
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1976')
        rules_mapping[rule]['debit'] = laac
        rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_1977', 'l10n_ch_elm_1978']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = transfer_salaries
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1979')
        rules_mapping[rule]['debit'] = is_tax
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_1980')
        rules_mapping[rule]['debit'] = prof_training
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_1200')
        rules_mapping[rule]['debit'] = provision_13th
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_1205')
        rules_mapping[rule]['debit'] = provision_14th
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_13_prov')
        rules_mapping[rule]['debit'] = month_13th
        rules_mapping[rule]['credit'] = provision_13th

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_14_prov')
        rules_mapping[rule]['debit'] = month_14th
        rules_mapping[rule]['credit'] = provision_14th

        for xml_id in [
            'l10n_ch_elm_2000', 'l10n_ch_elm_2005', 'l10n_ch_elm_2010',
            'l10n_ch_elm_2015', 'l10n_ch_elm_2020', 'l10n_ch_elm_2021', 'l10n_ch_elm_2022',
            'l10n_ch_elm_2000_net', 'l10n_ch_elm_2005_net', 'l10n_ch_elm_2010_net', 'l10n_ch_elm_2020_net',
        ]:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = social_insurance_payments
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_2050', 'l10n_ch_elm_2060']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = wages
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_2065')
        rules_mapping[rule]['debit'] = salary_pass_through
        rules_mapping[rule]['credit'] = wages

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_2075')
        rules_mapping[rule]['debit'] = wages
        rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in [
            'l10n_ch_elm_3000', 'l10n_ch_elm_3001', 'l10n_ch_elm_3004_fcf', 'l10n_ch_elm_3005_fcf',
            'l10n_ch_elm_3010', 'l10n_ch_elm_3011', 'l10n_ch_elm_3014_fcf', 'l10n_ch_elm_3015_fcf',
            'l10n_ch_elm_3030', 'l10n_ch_elm_3031', 'l10n_ch_elm_3032', 'l10n_ch_elm_3033',
            'l10n_ch_elm_3038', 'l10n_ch_elm_3035', 'l10n_ch_elm_3036', 'l10n_ch_elm_3037'
        ]:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = transfer_salaries
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in [
            'l10n_ch_elm_rule_5010', 'l10n_ch_elm_rule_5020', 'l10n_ch_elm_rule_5400', 'l10n_ch_elm_rule_compl_ac'
        ]:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = health_insurance_ahv
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in [
            'l10n_ch_elm_rule_7400', 'l10n_ch_elm_rule_7010', 'l10n_ch_elm_rule_7011',
            'l10n_ch_elm_rule_5020_comp', 'l10n_ch_elm_rule_compl_ac_comp'
        ]:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = ahv
            rules_mapping[rule]['credit'] = health_insurance_ahv

        for xml_id in [
            'l10n_ch_elm_rule_aap_comp', 'l10n_ch_elm_rule_5040_comp',
            'l10n_ch_elm_rule_laac_comp_1', 'l10n_ch_elm_rule_laac_comp_2'
        ]:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = aanp
            rules_mapping[rule]['credit'] = assurance_accident

        for xml_id in ['l10n_ch_elm_rule_5040', 'l10n_ch_elm_rule_laac1', 'l10n_ch_elm_rule_laac_2']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = assurance_accident
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_rule_ijm_1', 'l10n_ch_elm_rule_ijm_2']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = sickness_insurance
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_rule_ijm_comp_1', 'l10n_ch_elm_rule_ijm_comp_2']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = ijm
            rules_mapping[rule]['credit'] = sickness_insurance

        for xml_id in ['l10n_ch_hr_elm_5050', 'l10n_ch_hr_elm_5052']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = lpp_provision
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_hr_elm_7050', 'l10n_ch_hr_elm_7052']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = lpp
            rules_mapping[rule]['credit'] = lpp_provision

        for xml_id in ['l10n_ch_hr_elm_5111', 'l10n_ch_hr_elm_5112']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = lpp
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_hr_elm_5051')
        rules_mapping[rule]['debit'] = lpp_provision
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_hr_elm_7051')
        rules_mapping[rule]['debit'] = lpp
        rules_mapping[rule]['credit'] = lpp_provision

        for xml_id in ['l10n_ch_elm_rule_5061', 'l10n_ch_elm_rule_5061_nk', 'l10n_ch_elm_rule_5060', 'l10n_ch_elm_rule_5060_manual']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = source_tax
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_5070')
        rules_mapping[rule]['debit'] = health_insurance_caf
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_7070')
        rules_mapping[rule]['debit'] = health_insurance_caf
        rules_mapping[rule]['credit'] = fak

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_5080')
        rules_mapping[rule]['debit'] = salary_pass_through
        rules_mapping[rule]['credit'] = comp_company_car

        for xml_id in ['l10n_ch_elm_rule_5081', 'l10n_ch_elm_rule_5082']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_pass_through
            rules_mapping[rule]['credit'] = short_term_liabilities

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_5100')
        rules_mapping[rule]['debit'] = other_expenses
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_5110')
        rules_mapping[rule]['debit'] = wages
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_5310')
        rules_mapping[rule]['debit'] = transfer_salaries
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_7310')
        rules_mapping[rule]['debit'] = salary_pass_through
        rules_mapping[rule]['credit'] = transfer_salaries

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_5300')
        rules_mapping[rule]['debit'] = transfer_salaries
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_elm_rule_7300')
        rules_mapping[rule]['debit'] = salary_pass_through
        rules_mapping[rule]['credit'] = transfer_salaries

        for xml_id in ['l10n_ch_hr_elm_6000', 'l10n_ch_hr_elm_6020']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = fixed_rate_expenses
            rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_hr_elm_6030')
        rules_mapping[rule]['debit'] = other_expenses
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_hr_elm_6035')
        rules_mapping[rule]['debit'] = transfer_salaries
        rules_mapping[rule]['credit'] = salary_pass_through

        rule = self.env.ref('l10n_ch_hr_payroll.l10n_ch_hr_elm_6040')
        rules_mapping[rule]['debit'] = representation_fees
        rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_hr_elm_6050', 'l10n_ch_hr_elm_6070']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = fixed_rate_expenses
            rules_mapping[rule]['credit'] = salary_pass_through

        for xml_id in ['l10n_ch_elm_rule_6510', 'l10n_ch_elm_rule_6600']:
            rule = self.env.ref(f'l10n_ch_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_pass_through
            rules_mapping[rule]['credit'] = transfer_salaries

        self._configure_payroll_account(
            companies,
            "CH",
            account_refs=[
                salary_pass_through, transfer_salaries, health_insurance_ahv, short_term_liabilities, lpp_provision,
                health_insurance_caf, assurance_accident, sickness_insurance, source_tax, provision_13th,
                provision_14th, wages, social_insurance_payments, profit_sharing, month_13th, bonus, commissions,
                month_14th, ahv, fak, lpp, aanp, laac, ijm, is_tax, other_expenses, prof_training, travel_expenses,
                representation_fees, fixed_rate_expenses, rate_personal_use, comp_company_car, vehicle_expenses
            ],
            rules_mapping=rules_mapping,
        )
