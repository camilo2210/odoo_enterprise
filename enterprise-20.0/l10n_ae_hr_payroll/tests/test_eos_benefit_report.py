# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date


from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEOSBenefitReport(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ae_company = cls.env['res.company'].create({
            'name': 'AE Test Co',
            'city': 'Dubai',
            'country_id': cls.env.ref('base.ae').id,
        })

        cls.structure_type = cls.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').type_id.id
        cls.ae = cls.env.ref('base.ae')
        cls.env.user.write({
            'company_id': cls.ae_company.id,
            'company_ids': [(4, cls.ae_company.id)]
        })
        cls.env = cls.env(context=dict(cls.env.context,
                                        allowed_company_ids=[cls.ae_company.id]))

    def _create_employee(self, name, contract_date_start, date_version,
                         wage=10000.0, contract_date_end=False):
        vals = {
            'name': name,
            'company_id': self.ae_company.id,
            'country_id': self.ae.id,
            'contract_date_start': contract_date_start,
            'date_version': date_version,
            'wage': wage,
            'structure_type_id': self.structure_type,
        }
        if contract_date_end:
            vals['contract_date_end'] = contract_date_end
        return self.env['hr.employee'].create(vals)

    def _create_version(self, employee, contract_date_start, date_version,
                        wage=10000.0):
        return self.env['hr.version'].create({
            'employee_id': employee.id,
            'company_id': self.ae_company.id,
            'country_id': self.ae.id,
            'contract_date_start': contract_date_start,
            'date_version': date_version,
            'wage': wage,
            'structure_type_id': self.structure_type,
        })

    def _create_report(self, date_to=date(2027, 1, 1), employee_ids=None):
        return self.env['l10n.ae.eos.benefit.wizard'].create({
            'company_id': self.ae_company.id,
            'date_to': date_to,
            'employee_ids': employee_ids,
        })

    def test_report_computation(self):
        """
        Employee ids are provided normally, and the report is computed without any issues or
        missing salary rules.

        Three employees are created, one employee for each category of EOS benefit
        brackets: <1, 1-5, >5 years of service.

        One employee will have a single contract, another will have multiple contracts
        without gaps, and the last will have multiple contracts with gaps, to ensure that
        the report correctly computes different cases.

        - Employee 1: starts on 2026-01-02 and their contract does not end, with a wage of 10000.
        This employee will receive 0 EOSB for being in service.
        - Employee 2: starts on 2021-01-01, ends on 2021-12-31, and another contract starts
        on 2022-01-01 but does not end, with a wage of 10000. This employee will receive 45000
        EOSB for being in service for 5 years.
        - Employee 3: starts on 2020-01-01, ends on 2021-12-31, and another contract starts
        on 2024-01-01 but does not end. with a wage of 10000. This employee will receive 28000
        EOSB for being in service for 3 years which are the latter 3.
        """

        employee_1 = self._create_employee("Employee 1", date(2026, 1, 2), date(2026, 1, 2))
        employee_2 = self._create_employee("Employee 2", date(2021, 1, 1), date(2021, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_2, date(2022, 1, 1), date(2022, 1, 1))
        employee_3 = self._create_employee("Employee 3", date(2020, 1, 1), date(2020, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_3, date(2024, 1, 1), date(2024, 1, 1))
        report = self._create_report(employee_ids=[employee_1.id, employee_2.id, employee_3.id])
        report_data = report._get_report_data()
        expected_report_data = [
            {
                'employee_name': "Employee 1",
                'employee_id': employee_1.id,
                'first_contract_date': date(2026, 1, 2),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 0,
            },
            {
                'employee_name': "Employee 2",
                'employee_id': employee_2.id,
                'first_contract_date': date(2021, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 45000,
            },
            {
                'employee_name': "Employee 3",
                'employee_id': employee_3.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 21000,
            },
        ]
        self.assertEqual(report.issues, False)
        self.assertEqual(report_data, expected_report_data)

    def test_report_computation_without_employees(self):
        """
        Employee ids are not provided and are fetched automatically within the report,
        and the report is computed without any issues or missing salary rules.

        Three employees are created, one employee for each category of EOS benefit
        brackets: <1, 1-5, >5 years of service.

        One employee will have a single contract, another will have multiple contracts
        without gaps, and the last will have multiple contracts with gaps, to ensure that
        the report correctly computes different cases.

        - Employee 1: starts on 2026-01-02 and their contract does not end, with a wage of 10000.
        This employee will receive 0 EOSB for being in service.
        - Employee 2: starts on 2021-01-01, ends on 2021-12-31, and another contract starts
        on 2022-01-01 but does not end, with a wage of 10000. This employee will receive 45000
        EOSB for being in service for 5 years.
        - Employee 3: starts on 2020-01-01, ends on 2021-12-31, and another contract starts
        on 2024-01-01 but does not end. with a wage of 10000. This employee will receive 28000
        EOSB for being in service for 3 years which are the latter 3.
        """
        employee_1 = self._create_employee("Employee 1", date(2026, 1, 2), date(2026, 1, 2))
        employee_2 = self._create_employee("Employee 2", date(2021, 1, 1), date(2021, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_2, date(2022, 1, 1), date(2022, 1, 1))
        employee_3 = self._create_employee("Employee 3", date(2020, 1, 1), date(2020, 1, 1), contract_date_end=date(2021, 12, 31))
        self._create_version(employee_3, date(2024, 1, 1), date(2024, 1, 1))
        report = self._create_report()
        report_data = report._get_report_data()
        expected_report_data = [
            {
                'employee_name': "Employee 1",
                'employee_id': employee_1.id,
                'first_contract_date': date(2026, 1, 2),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 0.0,
            },
            {
                'employee_name': "Employee 2",
                'employee_id': employee_2.id,
                'first_contract_date': date(2021, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 45000.0,
            },
            {
                'employee_name': "Employee 3",
                'employee_id': employee_3.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 21000.0,
            },
        ]
        self.assertEqual(report.issues, False)
        self.assertEqual(report_data, expected_report_data)

    def test_report_computation_with_issues(self):
        """
        Employee ids are provided normally, but the report is computed with issues
        and without missing salary rules.

        Two employees are created, one employee with an issue while the other does not.

        One employee will have a single contract with end date before report date
        while the other will have normal running contract to ensure that the report
        correctly computes different cases.

        - Employee 1: starts on 2020-01-01 and ends on 2026-07-01, with a
        wage of 10000. This employee will receive 0 EOSB for being in service.
        - Employee 2: starts on 2020-01-01 but does not end, with a wage of
        10000. This employee will receive 45000 EOSB for being in service for 5 years.
        """
        employee_1 = self._create_employee("Employee 1", date(2020, 1, 1), date(2020, 1, 1), contract_date_end=date(2026, 7, 1))
        self.env["hr.employee.departure"].create({"employee_id": employee_1.id, "departure_date": date(2026, 7, 1)})
        employee_2 = self._create_employee("Employee 2", date(2020, 1, 1), date(2020, 1, 1))
        report = self._create_report(employee_ids=[employee_1.id, employee_2.id])
        report_data = report._get_report_data()
        expected_report_data = [
            {
                'employee_name': "Employee 1",
                'employee_id': employee_1.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 55000,
            },
            {
                'employee_name': "Employee 2",
                'employee_id': employee_2.id,
                'first_contract_date': date(2020, 1, 1),
                'selected_end_date': date(2027, 1, 1),
                'eosb_amount': 55000,
            },
        ]
        self.assertEqual(report.issues, True)
        self.assertEqual(report_data, expected_report_data)
