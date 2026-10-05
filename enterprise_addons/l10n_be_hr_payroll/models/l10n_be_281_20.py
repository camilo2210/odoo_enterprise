# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10n_Be281_20(models.Model):
    _name = 'l10n_be.281_20'
    _inherit = ['l10n_be.281.mixin']
    _description = 'HR Payroll 281.20 Wizard'

    def _get_declaration_code(self):
        return '281.20'

    def _get_eligible_employees(self, payslips):
        return payslips.filtered(
            lambda p: p.version_id.l10n_be_joint_committee_id.egov3_code == '999' and not p.version_id.l10n_be_include_employee_in_281_30
        ).employee_id

    def _get_line_codes(self):
        return ['GROSS', 'GROSS_NP', 'ATN_HOUSING_FISCAL', 'ATN_HEATING', 'ATN_ELEC', 'ATN.CAR', 'ATN.LAP', 'ATN.INT',
                'ATN.PHONE_AMT', 'ATN.TAB', 'ATN.MOB', 'ATN_RENT', 'GI.EMP.CONT', 'GI.EMP.VOL', 'P.P', 'P.P.NP', 'CYCLE', 'WARRANT_GROSS', 'WARRANT_PP']

    def _generate_employees_data(self, employee_payslips, all_line_values):
        self.ensure_one()
        res = super()._generate_employees_data(employee_payslips, all_line_values)
        employees_data = []

        line_codes = self._get_line_codes()

        for employee in employee_payslips:

            if employee in res['employees_with_error']:
                continue

            payslips = employee_payslips[employee]
            mapped_total = {
                code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                for code in line_codes}

            warrant_gross = sum(all_line_values['WARRANT_GROSS'][p.id]['total'] for p in payslips if p.struct_id.code == 'BEWARRANT')
            cct90_gross = sum(all_line_values['BONUS_GROSS'][p.id]['total'] for p in payslips if p.struct_id.code == 'BECCT90')

            cycle_days_amount = sum(all_line_values['CYCLE'][p.id]['total'] for p in payslips)
            if cycle_days_amount:
                cycle_km = sum(all_line_values['CYCLE'][p.id]['quantity'] * p.version_id.km_home_work * 2 for p in payslips)
            else:
                cycle_km = 0

            sheet_values = {
                'f2008_typefiche': '28120',
                'f20_2031_stopzettingexploitatie': 0,
                'f20_2033_optiebuitvennoots': '0',
                'f20_2035_verantwoordingsstukken': 0,
                'f20_2045_rsz': 0,
                'f20_2055_datumvanindienstt': 0,
                'f20_2056_datumvanvertrek': res['base_employees_data'][employee]['departure_date'],
                'f20_2060_periodieke': self._to_eurocent(round(mapped_total['GROSS'], 2)),
                'f20_2061_covidovertimeremuneration2023': 0,
                'f20_2062_anderebezoldiginge': self._to_eurocent(round(mapped_total['GROSS_NP'], 2)),
                'f20_2064_vervroegdvakantieg': 0,
                'f20_2065_opzeggingsreclasseringsverg': 0,
                'f20_2067_bijzonderbijdrage': 0,
                'f20_2069_compensationamountwithoutstandards': 0,
                'f20_2071_pensioengewonebijdragen': self._to_eurocent(round(mapped_total['GI.EMP.CONT'] + mapped_total['GI.EMP.VOL'], 2)),
                'f20_2073_periodieke': self._to_eurocent(round(mapped_total['ATN_RENT'], 2)),
                'f20_2074_anderen': 0,
                'f20_2076_nonrecurrentadvantages': self._to_eurocent(round(cct90_gross, 2)),
                'f20_2078_pensioentoezegging': 0,
                'f20_2079_bedrag': self._to_eurocent(round(warrant_gross, 2)),
                'f20_2080_bedrag': 0,
                'f20_2081_bezoldigingen': 0,
                'f20_2082_occasionalworkhoreca': 0,
                'f20_2083_bonus': 0,
                'f20_2084_bonus5254': 0,
                'f20_2087_code420': 0,
                'f20_2088_impulsfund': 0,
                'f20_2092_othercode1': '',
                'f20_2094_othercode2': '',
                'f20_2096_othercode3': '',
                'f20_2098_othercode4': '',
                'f20_2102_kas': '',
                'f20_2103_kasvrijaanvullendpensioen': '',
                'f20_2106_percentages': '00,00',
                'f20_2109_fiscaalidentificat': 0,
                'f20_2128_vrijaanvullendpensioenwerknemers': 0,
                'f20_2131_bedrijfsvoorheffingvanwerkgever': self._to_eurocent(round(abs(mapped_total['P.P']) + abs(mapped_total['P.P.NP']) + abs(mapped_total['WARRANT_PP']), 2)),
                'f20_2133_bedrijfsvoorheffingbuitenlvenverbondenwerkgever': 0,
                'f20_2134_totaalbedragmobiliteitsbudget': 0,
                'f20_2138_covidovertimehours2023': 0,
                'f20_2181_remunerationetrang': 0,
                'f20_2182_aandelenetrang': 0,
                'f20_2183_bonuspremieoaandelenoptiesetrang': 0,
                'f20_2184_anderevaaetrang': 0,
                'f20_2185_amountother1': 0,
                'f20_2186_amountother2': 0,
                'f20_2187_amountother3': 0,
                'f20_2188_amountother4': 0,
                'f20_2195_relanceovertimeremuneration': 0,
                'f20_2196_relanceovertimehours': 0,
                'f20_2200_compensationwithstandards': 0,
                'f20_2201_compensationwithdocuments': 0,
                'f20_2202_amount': 0,
                'f20_2203_amount': 0,
                'f20_2204_repaidsums': 0,
                'f20_2205_recuperation': 0,
                'f20_2206_grossamountremuneration': 0,
                'f20_2207_travelbicycleorspeedpedelec': self._to_eurocent(round(cycle_days_amount, 2)),
                'f20_2208_benefitprovisionbicycleorspeedpedelec': 0,
                'f20_2226_kmzone2207': str(int(cycle_km)),
                'f20_2227_relanceovertimeremuneration2025': 0,
                'f20_2228_relanceovertimehours2025': 0,
            }

            # ATNs
            atn_codes_mapping = {
                'ATN_HOUSING_FISCAL': 'B',
                'ATN_HEATING': 'C',
                'ATN_ELEC': 'D',
                'ATN.CAR': 'F',
                'ATN.LAP': 'H',
                'ATN.INT': 'I',
                'ATN.PHONE_AMT': 'J',
                'ATN.TAB': 'J',
                'ATN.MOB': 'K',
            }
            res_atn_total = 0
            res_atn_codes = ''
            for atn_code, report_code in atn_codes_mapping.items():
                atn_amount = mapped_total[atn_code]
                if atn_amount:
                    res_atn_total += atn_amount
                    res_atn_codes += report_code if not report_code in res_atn_codes else ''

            sheet_values['f20_2068_bedrag'] = self._to_eurocent(round(res_atn_total, 2))
            sheet_values['f20_2099_aard'] = res_atn_codes

            # Somme de la catégorie 6
            sheet_values['f20_2063_totaal'] = sum(sheet_values[code] for code in [
                'f20_2060_periodieke',
                'f20_2062_anderebezoldiginge',
                'f20_2068_bedrag',
                'f20_2079_bedrag',
                'f20_2080_bedrag',
                'f20_2204_repaidsums',
            ])

            # Somme de la catégorie 7
            sheet_values['f20_2075_totaal'] = sum(sheet_values[code] for code in [
                'f20_2073_periodieke',
                'f20_2074_anderen',
            ])

            # Somme de la catégorie 11
            sheet_values['f20_2209_totalcontributiontravelexpenses'] = sum(sheet_values[code] for code in [
                'f20_2207_travelbicycleorspeedpedelec',
                'f20_2208_benefitprovisionbicycleorspeedpedelec',
            ])

            # Somme de la catégorie 14
            sheet_values['f20_2066_totaalbedrijfsvoorheffing'] = sum(sheet_values[code] for code in [
                'f20_2131_bedrijfsvoorheffingvanwerkgever',
                'f20_2133_bedrijfsvoorheffingbuitenlvenverbondenwerkgever',
            ])

            # Somme de 2060 à 2088
            sheet_values['f20_2059_totaalcontrole'] = sum(
                sheet_values[code] for code in sheet_values if 'f20_2060' <= code <= 'f20_2088'
            )

            employees_data.append({**res['base_employees_data'][employee], **sheet_values})

        sum_2059 = sum(sheet_values['f20_2059_totaalcontrole'] for sheet_values in employees_data)
        sum_2066 = sum(sheet_values['f20_2066_totaalbedrijfsvoorheffing'] for sheet_values in employees_data)

        res.update({
            'employees_data': employees_data,
            'sum_control_total': sum_2059,
            'sum_withholding': sum_2066,
        })
        return res

    def _get_pdf_report(self):
        return self.env.ref('l10n_be_hr_payroll.action_report_employee_281_20')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        return self.env._('%(year)s-%(employee)s-281_20', year=self.declaration_id.year, employee=employee.name)
