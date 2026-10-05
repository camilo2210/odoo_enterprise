# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10n_Be281_13(models.Model):
    _name = 'l10n_be.281_13'
    _inherit = ['l10n_be.281.mixin']
    _description = 'HR Payroll 281.13 Wizard'

    def _get_declaration_code(self):
        return '281.13'

    def _get_eligible_employees(self, payslips):
        return payslips.filtered(
            lambda p: p.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.l10n_be_economic_unemployment)
        ).employee_id

    def _get_line_codes(self):
        return ['EUC', 'EUC_CP200', 'EUB', 'ECONOMIC_UNEMPLOYMENT.P.P']

    def _generate_employees_data(self, employee_payslips, all_line_values):
        self.ensure_one()

        res = super()._generate_employees_data(employee_payslips, all_line_values)
        employees_data = []

        line_codes = self._get_line_codes()

        for employee in employee_payslips:
            if employee in res['employees_with_error']:
                continue

            payslips = employee_payslips[employee]

            worked_days_lines = payslips.worked_days_line_ids.filtered(lambda w: w.work_entry_type_id.l10n_be_economic_unemployment)
            unemployment_number_of_days = sum(line.number_of_days for line in worked_days_lines)

            mapped_total = {0: {code: 0 for code in line_codes}, 1: {code: 0 for code in line_codes}}  # {regular, arrear salary}
            for payslip in payslips:
                for code in line_codes:
                    mapped_total[payslip.l10n_be_arrear_salary][code] += all_line_values[code][payslip.id]['total']

            sheet_values = {
                'f2008_typefiche': '28113',
                'f13_2031_repaymentneo': 0,
                'f13_2035_verantwoordingsstukken': 0,
                'f13_2059_totaalcontrole': 0,
                # Allocations
                'f13_2060_bedrag': mapped_total[0]['EUC'] + mapped_total[0]['EUC_CP200'] + mapped_total[0]['EUB'],
                'f13_2061_bedrag': 0,
                'f13_2064_bedrag': 0,
                'f13_2065_bedrag': 0,
                # Arriérés taxables distinctement
                'f13_2066_bedrag': mapped_total[1]['EUC'] + mapped_total[1]['EUC_CP200'] + mapped_total[1]['EUB'],
                'f13_2067_bedrag': 0,
                'f13_2070_bedrag': 0,
                'f13_2071_bedrag': 0,
                # total Soldes positifs à déclarer
                'f13_2072_werkloosheidzonder': mapped_total[0]['EUC'] + mapped_total[0]['EUC_CP200'] + mapped_total[0]['EUB'],  # 260
                'f13_2073_decemberallowance': 0,  # 304
                'f13_2074_werkloosheidmetancienniteit': 0,  # 264
                'f13_2075_werkloosheidzonder': mapped_total[1]['EUC'] + mapped_total[1]['EUC_CP200'] + mapped_total[1]['EUB'],  # 261 arrear salary
                'f13_2077_werkloosheidmetancienniteit': 0,  # 265
                # Withholding tax
                'f13_2078_bedrijfsvoorheffing': -(mapped_total[0]['ECONOMIC_UNEMPLOYMENT.P.P'] + mapped_total[1]['ECONOMIC_UNEMPLOYMENT.P.P']),  # 286
                # total Soldes négatifs
                'f13_2079_werkloosheidzonder': 0,  # 262
                'f13_2081_werkloosheidmetancienniteit': 0,
                'f13_2082_bijdragenpremies': 0,  # 285
                'f13_2083_voortzetting': 0,  # 283
                # Intervention dans les frais de déplacements des demandeurs d'emploi pour formation obligatoire..
                'f13_2084_movingexpenses': 0,
                # Nature (Work entries)
                'f13_2089_werkloosheidzonder': unemployment_number_of_days,
                'f13_2091_werkloosheidmetancienniteit': 0,
                'f13_2099_referentienummerui': '',
                'f13_2102_kas': '',
                'f13_2103_kasvrijaanvullendpensioen': '',
                'f13_2109_fiscaalidentificat': '',
                'f13_2128_vrijaanvullendpensioenwerknemers': '',  # 387
            }

            sheet_values['f13_2059_totaalcontrole'] = sum(
                sheet_values[code] for code in sheet_values if 'f13_2060' <= code <= 'f13_2088'
            )

            employees_data.append({**res['base_employees_data'][employee], **sheet_values})

        sum_2059 = sum(sheet_values['f13_2059_totaalcontrole'] for sheet_values in employees_data)
        sum_2078 = sum(sheet_values['f13_2078_bedrijfsvoorheffing'] for sheet_values in employees_data)

        res.update({
            'employees_data': employees_data,
            'sum_control_total': sum_2059,
            'sum_withholding': sum_2078,
        })
        return res

    def _get_pdf_report(self):
        return self.env.ref('l10n_be_hr_payroll.action_report_employee_281_13')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        return self.env._('%(year)s-%(employee)s-281_13', year=self.declaration_id.year, employee=employee.name)

    def _post_process_rendering_data_pdf(self, rendering_data):
        for sheet_values in rendering_data['employees_data']:
            for key, value in sheet_values.items():
                if key in ['f13_2089_werkloosheidzonder', 'f13_2091_werkloosheidmetancienniteit']:
                    sheet_values[key] = self.env._("%s days", value)
        return super()._post_process_rendering_data_pdf(rendering_data)
