from .common import TestSwissdecCommon

from odoo import fields
from odoo.tests.common import tagged

from freezegun import freeze_time
from dateutil.relativedelta import relativedelta
from datetime import date


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayslipEntryDate(TestSwissdecCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create
        # 1) An employee with two separated working periods in the company
        # 2) An employee with only 1 continuous working period
        # 3) An employee with no contract

        cls.gap_employee = cls.env['hr.employee'].create({
            'name': "Gap Employee",
        })
        cls.no_gap_employee = cls.env['hr.employee'].create({
            'name': "No Gap Employee",
        })
        cls.no_contract_employee = cls.env['hr.employee'].create({
            'name': "No Contract Employee",
        })

        with freeze_time("2026-01-01"):

            # Create working contracts with gap
            cls.gap_employee.create_version({
                'contract_date_start': fields.Date.today(),
                'contract_date_end': fields.Date.today() + relativedelta(days=5),
                'date_version': fields.Date.today(),
            })
            cls.gap_employee.create_version({
                'contract_date_start': fields.Date.today() + relativedelta(days=6),
                'contract_date_end': fields.Date.today() + relativedelta(days=15),
                'date_version': fields.Date.today() + relativedelta(days=6),
            })
            cls.gap_employee.create_version({
                'contract_date_start': fields.Date.today() + relativedelta(months=1),
                'contract_date_end': False,
                'date_version': fields.Date.today() + relativedelta(months=1),
            })

            # Create working contracts with no gap
            cls.no_gap_employee.create_version({
                'contract_date_start': fields.Date.today(),
                'contract_date_end': fields.Date.today() + relativedelta(months=1, days=-1),
                'date_version': fields.Date.today(),
            })
            cls.no_gap_employee.create_version({
                'contract_date_start': fields.Date.today() + relativedelta(months=1),
                'contract_date_end': False,
                'date_version': fields.Date.today() + relativedelta(months=1),
            })

    def test_payslip_entry_date(self):

        # Simulate generating January Payslip on the 27th of Jan
        with freeze_time("2026-01-27"):
            entry_date_gap_january = self.gap_employee._get_first_contract_date(fields.Date.today())
            entry_date_no_gap_january = self.no_gap_employee._get_first_contract_date(fields.Date.today())
            entry_date_no_contract_january = self.no_contract_employee._get_first_contract_date(fields.Date.today())
        # Simulate generating February Payslip on the 27th of Feb
        with freeze_time("2026-02-27"):
            entry_date_gap_february = self.gap_employee._get_first_contract_date(fields.Date.today())
            entry_date_no_gap_february = self.no_gap_employee._get_first_contract_date(fields.Date.today())
            entry_date_no_contract_february = self.no_contract_employee._get_first_contract_date(fields.Date.today())

        self.assertEqual(entry_date_gap_january, date(2026, 1, 1))
        self.assertEqual(entry_date_no_gap_january, date(2026, 1, 1))
        self.assertFalse(entry_date_no_contract_january)
        self.assertEqual(entry_date_gap_february, date(2026, 2, 1))
        self.assertEqual(entry_date_no_gap_february, date(2026, 1, 1))
        self.assertFalse(entry_date_no_contract_february)
