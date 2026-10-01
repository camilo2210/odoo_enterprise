# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10n_Be281_30(models.Model):
    _name = 'l10n_be.281_30'
    _inherit = ['l10n_be.281.mixin']
    _description = 'HR Payroll 281.30 Wizard'

    def _get_declaration_code(self):
        return '281.30'

    def _get_eligible_employees(self, payslips):
        return payslips.filtered(
            lambda p: p.version_id.l10n_be_include_employee_in_281_30
        ).employee_id

    def _get_line_codes(self):
        return ['PRESENCE_TOKEN', 'PRESENCE_TOKEN_WITHHOLDING_TAX', 'ATN_HOUSING', 'ATN_HEATING', 'ATN_ELEC', 'ATN.CAR',
                'ATN.LAP', 'ATN.INT', 'ATN.PHONE_AMT', 'ATN.TAB', 'ATN.MOB', 'ATN_RENT', 'PPTOTAL']

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

            sheet_values = {
                'f2008_typefiche': '28130',
                'f30_2030_beneficiarynature': 0,
                'f30_2035_verantwoordingsstukken': 0,
                'f30_2059_totaalcontrole': 0,
                'f30_2060_toegekendbedrag': 0,
                'f30_2061_vrijstelling': 0,
                'f30_2062_bedrag': 0,
                'f30_2063_bedrijfsvoorheffing': self._to_eurocent(round(mapped_total['PPTOTAL'], 2)),          # PRJPV (10)
                'f30_2064_presentiegelden': self._to_eurocent(round(mapped_total['PRESENCE_TOKEN'], 2)) if employee.l10n_be_resident_situation == 'resident' else 0,              # JEPRV (6a)
                'f30_2065_toegekendbedrag': 0,
                'f30_2066_vrijstelling': 0,
                'f30_2067_bedrag': 0,
                'f30_2068_zonderberoepskarak': 0,
                'f30_2069_bijzonderbijdrage': 0,
                'f30_2070_toegekendbedrag': 0,
                'f30_2071_vrijstelling': 0,
                'f30_2072_bedrag': 0,
                'f30_2073_toegekendbedrag': 0,
                'f30_2074_vrijstelling': 0,
                'f30_2075_bedrag': 0,
                'f30_2076_peronderhoudsuitke': 0,
                'f30_2077_onderhoudsuitkering': 0,
                'f30_2078_olympicbonus': 0,
                'f30_2079_totalamount': 0,
                'f30_2080_winstofbaten': 0,
                'f30_2081_retributies': self._to_eurocent(round(mapped_total['PRESENCE_TOKEN'], 2)) if employee.l10n_be_resident_situation == 'non_resident' else 0,                  # RETRV (7f)
                'f30_2082_buitverrichtingen': 0,
                'f30_2083_podiumkunstenaars': 0,            # RVAAV (7h)
                'f30_2084_winst': 0,                        # BEMAV (7m)
                'f30_2085_art2283': 0,
                'f30_2087_bedrag': 0,
                'f30_2088_bedrag': 0,
                'f30_2089_numberpeople': 0,                 # PE30B (8 personnes)
                'f30_2090_numberdays': 0,                   # JR30B (8 jours)
                'f30_2095_foreignolympicbonus': 0,
                'f30_2097_totalamount': 0,
                'f30_2109_fiscaalidentificat': 0,
                'f30_2113_sportlimitedremuneration': 0,     # RVASV (7i)
                'f30_2115_sportunlimitedotherremuneration': 0,
                'f30_2116_sportmorethan30daysprofit': 0,
                'f30_2117_managerprofit': 0,
                'f30_2205_recuperation': 0,
            }

            # ATNs
            atn_codes_mapping = {
                'ATN_HOUSING': 'B',
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
                    res_atn_codes += report_code if report_code not in res_atn_codes else ''

            sheet_values['f30_2086_bedrag'] = self._to_eurocent(round(res_atn_total, 2))    # RBFRV (9 montant)
            sheet_values['f30_2099_aard'] = res_atn_codes                                   # RBFRL (9 nature)

            # Somme de 2060 à 2088
            sheet_values['f30_2059_totaalcontrole'] = sum(
                sheet_values[code] for code in sheet_values if 'f30_2060' <= code <= 'f30_2088'
            )

            employees_data.append({**res['base_employees_data'][employee], **sheet_values})

        sum_2059 = sum(sheet_values['f30_2059_totaalcontrole'] for sheet_values in employees_data)
        sum_2063 = sum(sheet_values['f30_2063_bedrijfsvoorheffing'] for sheet_values in employees_data)

        res.update({
            'employees_data': employees_data,
            'sum_control_total': sum_2059,
            'sum_withholding': sum_2063,
        })
        return res

    def _get_pdf_report(self):
        return self.env.ref('l10n_be_hr_payroll.action_report_employee_281_30')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        return self.env._('%(year)s-%(employee)s-281_30', year=self.declaration_id.year, employee=employee.name)

    def _post_process_rendering_data_pdf(self, rendering_data):
        for sheet_values in rendering_data['employees_data']:
            for key, value in sheet_values.items():
                if key in ["f30_2089_numberpeople", "f30_2090_numberdays"]:
                    sheet_values[key] = f"{value}"
        return super()._post_process_rendering_data_pdf(rendering_data)
