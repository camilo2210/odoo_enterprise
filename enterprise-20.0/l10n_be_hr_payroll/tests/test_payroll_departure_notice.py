# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollDepartureNotice(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.pfi_employee = cls.env['hr.employee'].create({
            'name': 'PFI Employee',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'employee_type_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_pfi').id,
            'l10n_be_dimona_category': 'ivt',
        })

    def test_departure_notice_only_PFI(self):
        """
        When the employee only has one PFI contract, there is no notice period. The start and end date of the notice
        period should then be the departure date.
        """
        departure = self.env['hr.employee.departure'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=self.pfi_employee.id).create({
            'dismissal_date': date(2025, 2, 1),
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'departure_description': 'PFI fired',
        })
        self.assertEqual(departure.l10n_be_first_contract_id, self.env['hr.version'])
        self.assertFalse(departure.l10n_be_first_contract_date)
        self.assertEqual(departure.l10n_be_notice_period_start, date(2025, 2, 1),
            "If no notice period, the notice period start should be the dismissal date.")
        self.assertEqual(departure.departure_date, date(2025, 2, 1))
        self.assertEqual(departure.l10n_be_notice_duration_week_after_2014, 0)

    def test_departure_notice_first_PFI(self):
        """
        When the employee only has multiple contracts, including a PFI contract, the PFI contract should not be taken
        into account to compute the seniority.
        """
        self.pfi_employee.contract_date_end = date(2025, 1, 31)
        second_version_cdi = self.pfi_employee.create_version({
            'date_version': date(2025, 2, 1),
            'contract_date_start': date(2025, 2, 1),
            'employee_type_id': self.env.ref('hr.contract_type_employee').id,
            'l10n_be_dimona_category': 'oth',
        })
        wizard = self.env['hr.employee.departure'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=self.pfi_employee.id).create({
            'dismissal_date': date(2025, 3, 1),
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'departure_description': 'CDI fired',
        })
        self.assertEqual(wizard.l10n_be_first_contract_id, second_version_cdi)
        self.assertEqual(wizard.l10n_be_first_contract_date, date(2025, 2, 1))
