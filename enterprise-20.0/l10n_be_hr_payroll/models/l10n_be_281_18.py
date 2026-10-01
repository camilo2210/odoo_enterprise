# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models


_logger = logging.getLogger(__name__)

# Sources:
# - Technical Doc https://finances.belgium.be/fr/E-services/Belcotaxonweb/documentation-technique
# - "Avis aux débiteurs" https://finances.belgium.be/fr/entreprises/personnel_et_remuneration/avis_aux_debiteurs#q2


class L10n_Be281_18(models.Model):
    _name = 'l10n_be.281_18'
    _inherit = ['l10n_be.281.mixin']
    _description = 'HR Payroll 281.18 Wizard'

    def _get_declaration_code(self):
        return '281.18'

    def _get_eligible_employees(self, payslips):
        line_codes = self._get_line_codes()
        all_line_values = payslips._get_line_values(line_codes, extra_domain=self._get_fiscal_line_domain())
        eligible_employees = payslips.filtered(
            lambda p: any(all_line_values[code][p.id]['total'] for code in line_codes)
        ).employee_id
        return eligible_employees

    def _get_line_codes(self):
        return [
            'REPLACEMENT_REVENUE',
            'REPLACEMENT_REVENUE.P.P',
        ]

    def _generate_employees_data(self, employee_payslips, all_line_values):
        self.ensure_one()
        res = super()._generate_employees_data(employee_payslips, all_line_values)
        employees_data = []

        line_codes = self._get_line_codes()

        work_entry_type_codes = ['082.00', '072.00', '070.00', '082.01', '072.01']

        for employee in employee_payslips:

            if employee in res['employees_with_error']:
                continue

            payslips = employee_payslips[employee]

            mapped_total = {
                code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                for code in line_codes}

            worked_days_values = payslips._get_worked_days_line_values(work_entry_type_codes, ['number_of_days'])

            replacement_revenue_number_of_days = sum(worked_days_values[code][p.id]['number_of_days'] for p in payslips for code in work_entry_type_codes)

            sheet_values = {
                'f2008_typefiche': '28118',
                'f18_2035_verantwoordingsstukken': 0,
                'f18_2060_zonderclausulevergoedingen': 0,               # 292
                'f18_2061_zonderclausuleachterstallen': 0,              # 293
                'f18_2062_metclausulevergoedingen': 0,                  # 294
                'f18_2063_metclausuleachterstallen': 0,                 # 295
                'f18_2064_ziekteofinvaliditeit': self._to_eurocent(round(mapped_total['REPLACEMENT_REVENUE'], 2)),                 # 269
                'f18_2065_beroepsziekte': 0,                            # 270
                'f18_2066_anderegebeurtenissen': 0,                     # 271
                'f18_2067_belastbareachterstallen': 0,                  # 272
                'f18_2068_gewonebijdragen': 0,                          # 285
                'f18_2069_individuelevoortzettingbijdragen': 0,         # 283
                'f18_2070_bedrijfsvoorheffing': self._to_eurocent(round(-mapped_total['REPLACEMENT_REVENUE.P.P'], 2)),                  # 286
                'f18_2071_bijzonderebijdrage': 0,                       # 287
                'f18_2072_decembercompensationwithclause': 0,           # 300
                'f18_2073_decembercompensationwithoutclause': 0,        # 301
                'f18_2074_decembercompensation': 0,    # 302
                'f18_2075_vergoedingen_tot31122015': 0,                 # 319
                'f18_2076_vergoedingen_vanaf01012016': 0,               # 321
                'f18_2077_decembercompensation': 0,                     # 322
                'f18_2078_achterstallen': 0,                            # 324
                'f18_2079_vergoedingenvrijstelling': 0,
                'f18_2080_achterstallen_vanaf01012016': 0,              # 339
                'f18_2081_bonus': 0,                                    # 309
                'f18_2090_dagen': replacement_revenue_number_of_days,        # number of days for 269
                'f18_2091_dagen': 0,
                'f18_2102_kas': '',
                'f18_2103_kasvrijaanvullendpensioen': '',
                'f18_2109_fiscaalidentificat': '',  # Use NISS instead
                'f18_2128_vrijaanvullendpensioenwerknemers': 0,         # 387
            }

            # Somme de 2060 à 2088
            sheet_values['f18_2059_totaalcontrole'] = sum(sheet_values[code] for code in [
                'f18_2064_ziekteofinvaliditeit',
                'f18_2065_beroepsziekte',
                'f18_2070_bedrijfsvoorheffing'])

            employees_data.append({**res['base_employees_data'][employee], **sheet_values})

        sum_2059 = sum(sheet_values['f18_2059_totaalcontrole'] for sheet_values in employees_data)
        sum_2070 = sum(sheet_values['f18_2070_bedrijfsvoorheffing'] for sheet_values in employees_data)

        res.update({
            'employees_data': employees_data,
            'sum_control_total': sum_2059,
            'sum_withholding': sum_2070,
        })
        return res

    def _get_pdf_report(self):
        return self.env.ref('l10n_be_hr_payroll.action_report_employee_281_18')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        return self.env._('%(year)s-%(employee)s-281_18', year=self.declaration_id.year, employee=employee.name)

    def _post_process_rendering_data_pdf(self, rendering_data):
        result = {}
        data = self.declaration_id._get_main_data()
        for sheet_values in rendering_data['employees_data']:
            for key, value in sheet_values.items():
                if isinstance(value, int) and value == 0:
                    sheet_values[key] = '0.00 €'
                elif isinstance(value, float):
                    sheet_values[key] = f'{value:,.2f} €'
                elif not value:
                    sheet_values[key] = self.env._('None')
            result[sheet_values['employee']] = {**sheet_values, **data}
        return result
