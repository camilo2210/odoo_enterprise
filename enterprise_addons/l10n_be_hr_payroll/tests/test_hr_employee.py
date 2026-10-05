from freezegun import freeze_time

from odoo.tests import TransactionCase, Form, tagged
from odoo.exceptions import ValidationError
from datetime import date, datetime


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestHrEmployeeBelgiumForm(TransactionCase):

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.be_company = self.env['res.company'].create({
            'name': 'My Belgian Company - TEST',
            'country_id': self.env.ref('base.be').id,
        })
        self.env.user.write({
            'company_ids': [(4, self.be_company.id)],
            'company_id': self.be_company.id,
        })

    def test_belgian_employee_creation_via_form(self):
        with Form(self.env['hr.employee'].with_company(self.be_company)) as employee_form:
            employee_form.name = 'Tony Stark'
            employee_form.contract_date_start = '2025-01-01'
            employee_form.version_id.contract_date_start = '2025-01-01'
            employee_form.wage = 2500.0
            employee_form.employee_type_id = self.env.ref('hr.contract_type_employee')

        new_employee = employee_form.save()

        self.assertTrue(new_employee.id, "The employee did not save to the database!")
        self.assertEqual(new_employee.name, 'Tony Stark')
        self.assertEqual(str(new_employee.contract_date_start), '2025-01-01')

    @freeze_time('2026-09-01')
    def test_joint_committee_preserved_on_contract_start(self):
        committee = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        for default in (self.env['l10n.be.joint.committee'], self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')):
            self.be_company.current_payroll_config_id.l10n_be_main_joint_committee = default
            for start in (False, '2026-08-01'):
                with self.subTest(default=default, start=start):
                    with Form(self.env['hr.employee'].with_company(self.be_company)) as employee_form:
                        employee_form.name = 'Student'
                        employee_form.employee_type_id = self.env.ref('hr.contract_type_student')
                        employee_form.contract_date_start = start
                        employee_form.l10n_be_joint_committee_id = committee
                    employee = employee_form.record
                    self.assertEqual(employee.l10n_be_joint_committee_id, committee)
                    with Form(employee) as employee_form:
                        employee_form.contract_date_start = '2026-09-01'
                    self.assertEqual(employee.l10n_be_joint_committee_id, committee)

    def test_correct_niss_parsing(self):
        self.employee_nana = self.env['hr.employee'].create({
            'name': 'Nana',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
        })

        # Try a NISS with a valid date, it should save the value and update the birthday
        self.employee_nana.write({
            'niss': 88010119776,
        })

        self.assertEqual(self.employee_nana.niss, '88010119776')
        self.assertEqual(self.employee_nana.birthday, date(1988, 1, 1))

        # Reset birthday
        self.employee_nana.write({
            'birthday': False,
        })

        # Try NISS with no valid date, it should save the value but not update the birthday
        self.employee_nana.write({
            'niss': 88000119769,
        })

        self.assertEqual(self.employee_nana.niss, '88000119769')
        self.assertFalse(self.employee_nana.birthday)

        # Try invalid NISS, it should raise a ValidationError saying the NISS is invalid
        with self.assertRaises(ValidationError):
            self.employee_nana.write({
                'niss': 88000119760,
            })

    def test_default_payslip_language(self):
        """
        We verify that new employees have their payslip's language set by default to the environment's language if that language is part
        of the Belgian national languages i.e. French, Dutch or German.
        """
        # Also works with the 'fr_FR' and 'nl_NL' codes
        self.env['res.lang']._activate_lang('fr_BE')
        self.env['res.lang']._activate_lang('nl_BE')
        self.env['res.lang']._activate_lang('de_DE')

        employee_1 = self.env['hr.employee'].with_context(lang='en_US').create({
            'name': 'Emp 1',
        })
        employee_2 = self.env['hr.employee'].with_context(lang='fr_BE').create({
            'name': 'Emp 2',
        })
        employee_3 = self.env['hr.employee'].with_context(lang='nl_BE').create({
            'name': 'Emp 3',
        })
        employee_4 = self.env['hr.employee'].with_context(lang='de_DE').create({
            'name': 'Emp 4',
        })

        self.assertFalse(employee_1.lang, "The employee's payslip's language should not have any default value.")
        self.assertEqual(employee_2.lang, 'fr_BE', "The employee's payslip's language should be 'fr_BE' by default.")
        self.assertEqual(employee_3.lang, 'nl_BE', "The employee's payslip's language should be 'nl_BE' by default.")
        self.assertEqual(employee_4.lang, 'de_DE', "The employee's payslip's language should be 'de_DE' by default.")

    @freeze_time('2026-08-01')
    def test_create_public_holiday_allocation(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime(2026, 7, 31, 22, 0, 0),
            'date_to': datetime(2026, 8, 1, 21, 59, 59),
        })

        emp_flora, emp_stella, emp_musa = self.env['hr.employee'].create([
            {
                'name': 'Flora',
                'company_id': self.be_company.id,
                'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
            }, {
                'name': 'Stella',
                'company_id': self.be_company.id,
                'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
                'contract_date_start': date(2026, 1, 1),
            }, {
                'name': 'Musa',
                'company_id': self.be_company.id,
                'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
                'contract_date_start': date(2026, 1, 1),
                'contract_date_end': date(2026, 10, 1),
            }
        ])
        allocations_by_employee = dict(self.env['hr.leave.allocation']._read_group(
            domain=[
                ('employee_id', 'in', (emp_flora + emp_musa + emp_stella).ids),
                ('work_entry_type_id', 'any', [
                    ('code', '=', '006.15'),
                    ('country_id.code', '=', 'BE')
                ])
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset']
        ))
        self.assertFalse(allocations_by_employee.get(emp_flora))
        self.assertEqual(sum(allocations_by_employee.get(emp_stella).mapped('number_of_days')), 1)
        self.assertEqual(sum(allocations_by_employee.get(emp_musa).mapped('number_of_days')), 1)
