# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from datetime import date
from collections import defaultdict

from odoo import api, models


_logger = logging.getLogger(__name__)

# Sources:
# - Technical Doc https://finances.belgium.be/fr/E-services/Belcotaxonweb/documentation-technique
# - "Avis aux débiteurs" https://finances.belgium.be/fr/entreprises/personnel_et_remuneration/avis_aux_debiteurs#q2


class L10n_Be281_10(models.Model):
    _name = 'l10n_be.281_10'
    _inherit = ['l10n_be.281.mixin']
    _description = 'HR Payroll 281.10 Wizard'

    @api.model
    def _get_atn_nature(self, payslips):
        result = ''
        if any(payslip.version_id.housing_fiscal_amount for payslip in payslips):
            result += 'B'
        if any(payslip.version_id.heating_amount for payslip in payslips):
            result += 'C'
        if any(payslip.version_id.electricity_amount for payslip in payslips):
            result += 'D'
        if payslips._get_line_values(['ATN.CAR'], compute_sum=True)['ATN.CAR']['sum']['total']:
            result += 'F'
        if any(payslip.version_id.laptop for payslip in payslips):
            result += 'H'
        if any(payslip.version_id.internet for payslip in payslips):
            result += 'I'
        if any(payslip.version_id.tablet or payslip.version_id.mobile_amount for payslip in payslips):
            result += 'J'
        if any(payslip.version_id.mobile for payslip in payslips):
            result += 'K'
        if any(payslip.version_id.rent_amount or payslip.version_id.pension_amount for payslip in payslips):
            result += 'Z'
        return result

    def _get_declaration_code(self):
        return '281.10'

    def _get_eligible_employees(self, payslips):
        return payslips.filtered(
            lambda p: p.version_id.l10n_be_joint_committee_id.egov3_code != '999' and not p.version_id.l10n_be_include_employee_in_281_30
        ).employee_id

    def _get_line_codes(self):
        return [
            'NET', 'PAY_SIMPLE', 'PPTOTAL', 'M.ONSS', 'ATN.INT', 'ATN.MOB', 'ATN.PHONE_AMT', 'ATN.LAP', 'ATN.TAB', 'CYCLE',
            'ATN.CAR', 'ATNCARREGUL', 'ATN_ELEC', 'ATN_HEATING', 'ATN_HOUSING_FISCAL', 'ATN_RENT', 'ATN_PENSION', 'REP.FEES', 'REP.FEES.VOLATILE', 'PUB.TRANS', 'TRAIN', 'CAR.PRIV', 'FUEL_CARD_COMMUTE', 'TRANSPORT_3P', 'EmpBonus.1', 'GROSS',
            'DH_GROSS', 'GROSS_NP', 'BONUS_GROSS', 'WARRANT_GROSS', 'TERM_GROSS', 'HOLIDAY_TERM_GROSS', 'DH_PP', 'ONSS', 'SALARY', 'EmpBonus.A', 'EmpBonus.B', 'GI.EMP.CONT', 'GI.EMP.VOL', 'VOLOTNOONSS', 'REPLACEMENT_REVENUE.P.P', 'EXPENSE_MANUAL'
        ]

    def _generate_employees_data(self, employee_payslips, all_line_values):
        self.ensure_one()
        res = super()._generate_employees_data(employee_payslips, all_line_values)
        employees_data = []

        year = self.declaration_id.year

        total_employee_contribution = 0
        line_codes = self._get_line_codes()

        warrant_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant')
        holiday_n_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        holiday_n1_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')
        termination_fees_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        cct90_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_cct90')

        other_transport_exemption_by_niss = defaultdict(lambda: 0)

        employees = self.env['hr.employee'].browse().union(employee_payslips.keys())
        mobility_budget_total_amount_by_employee = employees._get_l10n_be_mobility_budget_amount_prorated(year=year)

        for employee in employee_payslips:

            if employee in res['employees_with_error']:
                continue

            payslips = employee_payslips[employee]

            mapped_total = {
                code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                for code in line_codes}
            total_employee_contribution += mapped_total.get('GI.EMP.CONT', 0)

            all_gross_codes = self.env['hr.payslip']._get_gross_wage_line_codes()
            total_gross = sum(mapped_total[code] for code in all_gross_codes)
            warrant_gross = sum(all_line_values['WARRANT_GROSS'][p.id]['total'] for p in payslips if p.struct_id == warrant_structure)
            holiday_gross = sum(all_line_values['HOLIDAY_TERM_GROSS'][p.id]['total'] for p in payslips if p.struct_id in holiday_n_structure + holiday_n1_structure)
            termination_gross = sum(all_line_values['TERM_GROSS'][p.id]['total'] for p in payslips if p.struct_id in termination_fees_structure)
            cct90_gross = sum(all_line_values['BONUS_GROSS'][p.id]['total'] for p in payslips if p.struct_id == cct90_structure)
            arrear_gross = sum(all_line_values['GROSS'][p.id]['total'] for p in payslips if p.l10n_be_arrear_salary)
            common_gross = total_gross - warrant_gross - holiday_gross - termination_gross - cct90_gross - arrear_gross

            first_contract_date = employee._get_first_contract_date(date_limit=date(int(year), 12, 31))
            # 2021: Only private car
            # from 2022: private car / company car (from May)
            max_other_transport_exemption = self.env['hr.rule.parameter']._get_parameter_from_code(
                'pricate_car_taxable_threshold',
                date=date(int(year), 1, 1))
            start = first_contract_date
            end = date(int(year), 12, 31)
            number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
            number_of_month = min(12, number_of_month)
            other_transport_exemption = 0
            has_company_car = bool(round(mapped_total['ATN.CAR'], 2))
            fuel_card_commute = mapped_total['FUEL_CARD_COMMUTE']
            private_transport_reimbursement = mapped_total['CAR.PRIV'] + fuel_card_commute
            has_private_car = bool(round(private_transport_reimbursement, 2)) and not has_company_car
            if round(private_transport_reimbursement, 2) + round(mapped_total['ATN.CAR'], 2):
                other_transport_exemption = max_other_transport_exemption  # * number_of_month / 12.0

            cycle_days_amount = sum(all_line_values['CYCLE'][p.id]['total'] for p in payslips)
            if cycle_days_amount:
                cycle_km = sum(all_line_values['CYCLE'][p.id]['quantity'] * p.version_id.km_home_work * 2 for p in payslips)
            else:
                cycle_km = 0

            mobility_budget_total_amount = mobility_budget_total_amount_by_employee.get(employee.id, 0)

            diff_to_atn = 0
            private_car_to_atn = 0
            if has_private_car:
                other_transport_mean = max(0, private_transport_reimbursement)
            else:
                other_transport_mean = min(private_transport_reimbursement + mapped_total['ATN.CAR'], other_transport_exemption)
                # private transport reimbursement is not exempted
                other_transport_mean = max(other_transport_mean, private_transport_reimbursement)
                other_transport_exemption_by_niss[employee.niss] += max(other_transport_mean - private_transport_reimbursement, 0)
                if private_transport_reimbursement and mapped_total['ATN.CAR']:
                    private_car_to_atn += private_transport_reimbursement
                if other_transport_exemption_by_niss[employee.niss] > max_other_transport_exemption:
                    diff_to_atn += other_transport_exemption_by_niss[employee.niss] - max_other_transport_exemption
                other_transport_mean = other_transport_mean - diff_to_atn
            private_car_to_atn = min(private_car_to_atn, max_other_transport_exemption)

            sheet_values = {
                'f2008_typefiche': '28110',
                'f10_2031_associationactivity': 0,
                'f10_2035_verantwoordingsstukken': 0,
                'f10_2036_inwonersdeenfr': 0,
                'f10_2037_vergoedingkosten': 0,
                'f10_2038_seasonalworker': 0,
                'f10_2039_optiebuitvennoots': '0',
                'f10_2040_individualconvention': 0,
                'f10_2041_overheidspersoneel': 0,
                'f10_2042_sailorcode': 0,
                'f10_2045_code': 0,
                # 'f10_2055_datumvanindienstt': employee.first_contract_date.strftime('%d/%m/%Y') if employee.first_contract_date.year == self.year else '',
                'f10_2055_datumvanindienstt': first_contract_date.strftime('%d-%m-%Y') if first_contract_date else '',
                'f10_2056_datumvanvertrek': employee.departure_date.strftime('%d-%m-%Y') if employee.departure_date and employee.departure_date > first_contract_date else '',
                # f10_2059_totaalcontrole
                'f10_2060_gewonebezoldiginge': self._to_eurocent(round(common_gross, 2)),
                'f10_2061_bedragoveruren300horeca': 0,
                # f10_2062_totaal
                'f10_2063_vervroegdvakantieg': self._to_eurocent(round(holiday_gross, 2)),
                'f10_2064_afzbelachterstall': self._to_eurocent(round(arrear_gross, 2)),
                'f10_2065_opzeggingsreclasseringsverg': self._to_eurocent(round(termination_gross, 2)),
                'f10_2066_impulsfund': 0,
                'f10_2067_rechtvermindering66_81': 0,
                'f10_2068_rechtvermindering57_75': 0,
                'f10_2069_fidelitystamps': 0,
                'f10_2070_decemberremuneration': 0,
                'f10_2072_pensioentoezetting':  0,
                'f10_2073_tipamount': 0,
                'f10_2074_bedrijfsvoorheffing': self._to_eurocent(round(mapped_total['PPTOTAL'] - abs(mapped_total['DH_PP']) - abs(mapped_total['REPLACEMENT_REVENUE.P.P']), 2)),  # 2.074 = 2.131 + 2.133. YTI Is it ok to include PROF_TAX / should include Double holidays?
                'f10_2075_bijzonderbijdrage': self._to_eurocent(round(-mapped_total['M.ONSS'], 2)),
                # 6b) ATN
                'f10_2076_voordelenaardbedrag': self._to_eurocent(
                    max(
                        0,
                        round(sum(mapped_total[code] for code in ['ATN.INT', 'ATN.MOB', 'ATN.PHONE_AMT', 'ATN.LAP', 'ATN.TAB', 'ATN.CAR', 'ATNCARREGUL', 'ATN_ELEC', 'ATN_HEATING', 'ATN_HOUSING_FISCAL', 'ATN_RENT', 'ATN_PENSION']) + diff_to_atn - other_transport_exemption + private_car_to_atn, 2) if has_company_car else round(sum(mapped_total[code] for code in ['ATN.INT', 'ATN.MOB', 'ATN.PHONE_AMT', 'ATN.LAP', 'ATN.TAB', 'ATN.CAR', 'ATNCARREGUL', 'ATN_ELEC', 'ATN_HEATING', 'ATN_HOUSING_FISCAL', 'ATN_RENT', 'ATN_PENSION']), 2))),
                # f10_2077_totaal
                'f10_2078_compensationamountwithoutstandards': self._to_eurocent(round(mapped_total['REP.FEES.VOLATILE'], 2)),
                'f10_2079_covidovertimeremuneration2023': 0,
                'f10_2081_gewonebijdragenenpremies': self._to_eurocent(round(mapped_total['GI.EMP.CONT'] + mapped_total['GI.EMP.VOL'], 2)),
                'f10_2082_bedrag': self._to_eurocent(round(warrant_gross, 2)),
                'f10_2083_bedrag': 0,
                'f10_2084_mobiliteitsvergoedi': 0,
                'f10_2085_forfbezoldiging': 0,
                # Box 14a also includes the third party paid transport subscription (declared like public transport).
                'f10_2086_openbaargemeenschap': self._to_eurocent(round(mapped_total['PUB.TRANS'] + mapped_total['TRANSPORT_3P'], 2)),
                'f10_2087_bedrag': 0,
                # 14) Autre moyen de transport
                'f10_2088_andervervoermiddel': self._to_eurocent(round(other_transport_mean, 2)),
                'f10_2090_outborderdays': 0,
                'f10_2092_othercode1': 0,
                'f10_2094_othercode2': 0,
                'f10_2095_aantaluren': 0,
                'f10_2096_othercode3': 0,
                'f10_2097_aantaluren': 0,
                'f10_2098_othercode4': 0,
                'f10_2099_aard': self._get_atn_nature(payslips),
                'f10_2102_kas': 0,
                'f10_2103_kasvrijaanvullendpensioen': 0,
                'f10_2106_percentages': '00,00' if self._to_eurocent(round(warrant_gross, 2)) else '',  # Note: No percentages for warrants
                'f10_2109_fiscaalidentificat': '', # Use NISS instead
                'f10_2110_aantaloveruren360': 0,
                'f10_2111_achterstalloveruren300horeca': 0,
                'f10_2113_forfaitrsz': 0,
                'f10_2115_bonus': self._to_eurocent(round(mapped_total['EmpBonus.A'], 2)),
                'f10_2116_badweatherstamps': 0,
                'f10_2117_nonrecurrentadvantages': self._to_eurocent(round(cct90_gross, 2)),
                'f10_2118_overtimehours180': 0,
                'f10_2119_sportremuneration': 0,
                'f10_2120_sportvacancysavings': 0,
                'f10_2121_sportoutdated': 0,
                'f10_2122_sportindemnificationofretraction': 0,
                'f10_2123_managerremuneration': 0,
                'f10_2124_managervacancysavings': 0,
                'f10_2125_manageroutdated': 0,
                'f10_2126_managerindemnificationofretraction': 0,
                'f10_2127_nonrecurrentadvantagesoutdated': 0,
                'f10_2128_vrijaanvullendpensioenwerknemers': 0,
                'f10_2129_exemptincomesubjecttoprogressivity': 0,
                'f10_2130_privatepc': 0,
                'f10_2131_bedrijfsvoorheffingvanwerkgever': self._to_eurocent(round(mapped_total['PPTOTAL'] - abs(mapped_total['DH_PP']) - abs(mapped_total['REPLACEMENT_REVENUE.P.P']), 2)),
                'f10_2132_horeca': 0,
                'f10_2133_bedrijfsvoorheffingbuitenlvenverbondenwerkgever': 0,
                'f10_2134_totaalbedragmobiliteitsbudget': self._to_eurocent(round(mobility_budget_total_amount, 2)),
                'f10_2136_amountcontractofstudent': 0,
                'f10_2137_amountstudentspecificperiod': 0,
                'f10_2138_covidovertimehours2023': 0,
                'f10_2141_total': 0,
                'f10_2142_totalovertimehours180': 0,
                'f10_2143_bedragoveruren360horeca': 0,
                'f10_2165_achterstalloveruren360horeca': 0,
                'f10_2166_flexi_job': 0,
                'f10_2167_aantaloveruren300horeca': 0,
                'f10_2168_achterstallaantaloveruren300horeca': 0,
                'f10_2169_aantaloveruren360horeca': 0,
                'f10_2170_achterstallaantaloveruren360horeca': 0,
                'f10_2176_overtimehours180': 0,
                'f10_2177_winstpremies': 0,
                'f10_2178_pensioner': 0,
                'f10_2179_startersjob': 0,
                'f10_2180_onkostenbrandweerenambulanciers': 0,
                'f10_2181_remunerationetrang': 0,
                'f10_2182_aandelenetrang': 0,
                'f10_2183_bonuspremieoaandelenoptiesetrang': 0,
                'f10_2184_anderevaaetrang': 0,
                'f10_2185_amountother1': 0,
                'f10_2186_amountother2': 0,
                'f10_2187_amountother3': 0,
                'f10_2188_amountother4': 0,
                'f10_2195_relanceovertimeremuneration': self._to_eurocent(max(round(mapped_total['VOLOTNOONSS'], 2), 0)),
                'f10_2196_relanceovertimehours': self._to_eurocent(round(sum(wd.number_of_hours for wd in payslips.worked_days_line_ids if wd.code == '039.23'), 2)),
                'f10_2198_flexijobnotpension': 0,
                'f10_2200_compensationwithstandards': self._to_eurocent(round(mapped_total['REP.FEES'], 2)),
                'f10_2201_compensationwithdocuments': self._to_eurocent(round(mapped_total['EXPENSE_MANUAL'], 2)),
                'f10_2202_amount': 0,
                'f10_2203_amount': 0,
                'f10_2204_repaidsums': 0,
                'f10_2206_grossamountremuneration': 0,
                'f10_2207_travelbicycleorspeedpedelec': self._to_eurocent(round(cycle_days_amount, 2)),
                'f10_2208_benefitprovisionbicycleorspeedpedelec': 0,
                'f10_2209_overtimehours': 0,
                'f10_2210_workbonus5254': self._to_eurocent(max(round(mapped_total['EmpBonus.B'], 2), 0)),
                'f10_2226_kmzone2207': int(cycle_km),
                'f10_2227_relanceovertimeremuneration2025': self._to_eurocent(max(round(sum(all_line_values['VOLOTNOONSS'][p.id]['total'] for p in payslips if p.date_from.year == 2025), 2), 0)),
                'f10_2228_relanceovertimehours2025': self._to_eurocent(round(sum(wd.number_of_hours for wd in payslips.worked_days_line_ids if wd.code == '039.23' and wd.date_from.year == 2025), 2)),
            }

            # Somme de 2.060 + 2.076 + 2069 + 2.082 + 2.083 + 2204
            sheet_values['f10_2062_totaal'] = sum(sheet_values[code] for code in [
                'f10_2060_gewonebezoldiginge',
                'f10_2076_voordelenaardbedrag',
                'f10_2069_fidelitystamps',
                'f10_2082_bedrag',
                'f10_2083_bedrag',
                'f10_2204_repaidsums'])

            # Somme de 2.086 + 2.087 + 2.088
            sheet_values['f10_2077_totaal'] = sum(sheet_values[code] for code in [
                'f10_2086_openbaargemeenschap',
                'f10_2087_bedrag',
                'f10_2088_andervervoermiddel',
                'f10_2207_travelbicycleorspeedpedelec',
                'f10_2208_benefitprovisionbicycleorspeedpedelec',
            ])

            # Somme de 2060 à 2088, f10_2062_totaal et f10_2077_totaal inclus
            sheet_values['f10_2059_totaalcontrole'] = sum(sheet_values[code] for code in [
                'f10_2060_gewonebezoldiginge',
                'f10_2061_bedragoveruren300horeca',
                'f10_2062_totaal',
                'f10_2063_vervroegdvakantieg',
                'f10_2064_afzbelachterstall',
                'f10_2065_opzeggingsreclasseringsverg',
                'f10_2066_impulsfund',
                'f10_2067_rechtvermindering66_81',
                'f10_2068_rechtvermindering57_75',
                'f10_2069_fidelitystamps',
                'f10_2070_decemberremuneration',
                'f10_2072_pensioentoezetting',
                'f10_2073_tipamount',
                'f10_2074_bedrijfsvoorheffing',
                'f10_2075_bijzonderbijdrage',
                'f10_2076_voordelenaardbedrag',
                'f10_2077_totaal',
                'f10_2078_compensationamountwithoutstandards',
                'f10_2081_gewonebijdragenenpremies',
                'f10_2082_bedrag',
                'f10_2083_bedrag',
                'f10_2084_mobiliteitsvergoedi',
                'f10_2085_forfbezoldiging',
                'f10_2086_openbaargemeenschap',
                'f10_2087_bedrag',
                'f10_2088_andervervoermiddel'])

            employees_data.append({**res['base_employees_data'][employee], **sheet_values})

        sum_2059 = sum(sheet_values['f10_2059_totaalcontrole'] for sheet_values in employees_data)
        sum_2074 = sum(sheet_values['f10_2074_bedrijfsvoorheffing'] for sheet_values in employees_data)

        # Set the total employee contribution sum for all employees (if needed globally)
        for sheet_values in employees_data:
            sheet_values['f10_2257_employeecontribution'] = self._to_eurocent(round(total_employee_contribution, 2))

        res.update({
            'employees_data': employees_data,
            'sum_control_total': sum_2059,
            'sum_withholding': sum_2074,
        })
        return res

    def _get_pdf_report(self):
        return self.env.ref('l10n_be_hr_payroll.action_report_employee_281_10')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        return self.env._('%(year)s-%(employee)s-281_10', year=self.declaration_id.year, employee=employee.name)

    def _post_process_rendering_data_pdf(self, rendering_data):
        for sheet_values in rendering_data['employees_data']:
            for key, value in sheet_values.items():
                if key == "f10_2090_outborderdays":
                    sheet_values[key] = self.env._("%s days", value)
        return super()._post_process_rendering_data_pdf(rendering_data)
