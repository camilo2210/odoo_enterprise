# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSwissdecMissingValues(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Swiss Company',
            'country_id': cls.env.ref('base.ch').id,
        })
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Hans Muster',
            'registration_number': '12',
            'company_id': cls.company.id,
        })
        cls.report = cls.env['ch.yearly.report'].create({'name': 'Yearly Declaration', 'company_id': cls.company.id})

    def _missing(self, record, field, employee=None):
        return {
            "_missing_": True,
            "res_model": record._name,
            "res_id": record.id,
            "res_field": field,
            "employee_id": employee.id if employee else None,
        }

    def test_missing_values(self):
        version = self.employee.version_id
        birthday = self._missing(self.employee, 'birthday')
        self.report.l10n_ch_declare_salary_data = {"Staff": {"Person": [{
            "Particulars": {
                "EmployeeNumber": "12",
                "DateOfBirth": birthday,
                "Nationality": self._missing(version, 'country_id', self.employee),
            },
            "UVG-LAA-Salaries": {"UVG-LAA-Salary": [
                {"UVG-LAA-Code": self._missing(version, 'l10n_ch_laa_group', self.employee)},
                # the same value missing twice is only listed once
                {"UVG-LAA-Code": self._missing(version, 'l10n_ch_laa_group', self.employee)},
            ]},
            "TaxSalaries": {"TaxSalary": [{"Particulars": {"DateOfBirth": birthday}}]},
        }]}}

        warnings = list(self.report.actionable_warnings.values())
        self.assertEqual(len(warnings), 1, "The missing values should be detailed in a single warning")
        missing_values = warnings[0]['missing_values']
        self.assertEqual([missing_value['key'] for missing_value in missing_values], [
            f"hr.employee,{self.employee.id},birthday",
            f"hr.version,{version.id},country_id",
            f"hr.version,{version.id},l10n_ch_laa_group",
        ])
        self.assertEqual({missing_value['employee_name'] for missing_value in missing_values}, {'Hans Muster'})
        self.assertEqual(missing_values[0]['label'], self.env['hr.employee']._fields['birthday']._description_string(self.env))

        employee_action, version_action = missing_values[0]['action'], missing_values[1]['action']
        self.assertEqual((employee_action['res_model'], employee_action['res_id']), ('hr.employee', self.employee.id))
        self.assertEqual((version_action['res_model'], version_action['res_id']), ('hr.employee', self.employee.id))
        self.assertEqual(version_action['context']['version_id'], version.id, "The version to complete should be opened")

        with self.assertRaises(ValidationError):
            self.report._validate_declaration()

    def test_missing_value_without_record(self):
        self.report.l10n_ch_declare_salary_data = {"Staff": {"Person": [{
            "Particulars": {"EmployeeNumber": "12", "DateOfBirth": {"_missing_": True}},
        }]}}
        warnings = list(self.report.actionable_warnings.values())
        self.assertEqual(len(warnings), 1, "A value missing without record to complete still blocks the declaration")
        self.assertEqual(warnings[0]['missing_values'], [])

    def test_complete_missing(self):
        birthday = self._missing(self.env['l10n.ch.hr.employee.children'], 'birthdate')
        canton = self._missing(self.employee.version_id, 'l10n_ch_canton', self.employee)
        previous = {"City": "Zurich", "Canton": canton, "Children": [{"Firstname": "Anna", "DateOfBirth": birthday}]}
        current = {"City": "Bern", "Children": [
            {"Firstname": "Lea", "DateOfBirth": "2021-03-04"},
            {"Firstname": "Anna", "DateOfBirth": "2019-01-02"},
        ]}
        self.assertEqual(self.env['l10n.ch.employee.monthly.values']._complete_missing(previous, current), {
            "City": "Zurich",
            "Canton": canton,
            "Children": [{"Firstname": "Anna", "DateOfBirth": "2019-01-02"}],
        }, "Only the missing values found in the current data should be completed")

    @freeze_time('2025-06-16')
    def test_refresh_missing_data(self):
        employee = self.env['hr.employee'].create({
            'name': 'Anna Meier',
            'registration_number': '13',
            'company_id': self.company.id,
            'contract_date_start': date(2025, 1, 1),
            'structure_type_id': self.env.ref('l10n_ch_hr_payroll.structure_type_employee_ch').id,
        })
        employee.with_context(l10n_ch_reference_date=date(2025, 1, 1))._create_or_update_snapshot()
        january = self.env['l10n.ch.employee.yearly.values'].search([
            ('employee_id', '=', employee.id),
            ('year', '=', 2025),
        ]).monthly_value_ids.filtered(lambda snapshot: snapshot.month == 1)

        # the payslip of January was validated before the data was completed
        january.payroll_month_closed = True
        employee.write({'birthday': date(1990, 5, 17), 'l10n_ch_legal_last_name': 'Muster'})
        self.assertTrue(january.person['Particulars']['DateOfBirth'].get('_missing_'))

        report = self.env['ch.yearly.report'].create({'name': 'Yearly Declaration', 'company_id': self.company.id, 'year': 2025})
        report.action_refresh_missing_data()
        self.assertEqual(january.person['Particulars']['DateOfBirth'], '1990-05-17')
        self.assertEqual(january.employee_meta_data['Particulars']['DateOfBirth'], '1990-05-17')
        self.assertEqual(january.person['Particulars']['Lastname'], 'Meier', "The values of a closed period should be kept")
