# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestPayrollFuelCardPrivateUse(TestPayrollCommon):

    def test_fuel_card_personal_use_default_applied_to_payslip(self):
        with freeze_time('2026-01-20'):
            employee = self.create_employee({
                'name': 'Fuel Card Private Use employee',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'fuel_card': 150.0,
                'fuel_card_personal_use': 50.0,
            })
            version = employee.version_id
            self.assertFalse(version.transport_mode_car, "Expected no company car on this version")
            self.assertEqual(version.fuel_card, 150.0)
            self.assertEqual(version.fuel_card_personal_use, 50.0)

            slip = self.env['hr.payslip'].create({
                'name': f"Payslip {employee.name} 2026-01",
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': version.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            slip.compute_sheet()

            line = slip.line_ids.filtered(lambda l: l.code == 'FUEL_CARD_PRIV')
            self.assertTrue(
                line,
                "The FUEL_CARD_PRIV rule should fire on the payslip: the employee has a "
                "fuel_card_personal_use default value set on the payroll tab, no company car.")
            self.assertEqual(
                line.total, 50.0,
                "The FUEL_CARD_PRIV salary input should default to the employee's "
                "fuel_card_personal_use value, not stay at 0.")

    def test_fuel_card_personal_use_ignored_with_company_car(self):
        with freeze_time('2026-01-20'):
            employee = self.create_employee({
                'name': 'Fuel Card Private Use employee with car',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'fuel_card': 150.0,
                'fuel_card_personal_use': 50.0,
                'transport_mode_car': True,
            })
            version = employee.version_id

            slip = self.env['hr.payslip'].create({
                'name': f"Payslip {employee.name} 2026-01",
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': version.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            slip.compute_sheet()

            line = slip.line_ids.filtered(lambda l: l.code == 'FUEL_CARD_PRIV')
            self.assertFalse(
                line,
                "FUEL_CARD_PRIV must not fire when the employee has a company car: "
                "the car's own benefit-in-kind already covers the fuel card.")

    def test_fuel_card_personal_use_ignored_with_mobility_budget(self):
        with freeze_time('2026-01-20'):
            employee = self.create_employee({
                'name': 'Fuel Card Private Use employee mobility budget',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'fuel_card': 150.0,
                'fuel_card_personal_use': 50.0,
                'l10n_be_mobility_budget': True,
            })
            version = employee.version_id
            self.assertTrue(version.l10n_be_mobility_budget)

            slip = self.env['hr.payslip'].create({
                'name': f"Payslip {employee.name} 2026-01",
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': version.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            slip.compute_sheet()

            line = slip.line_ids.filtered(lambda l: l.code == 'FUEL_CARD_PRIV')
            self.assertFalse(
                line,
                "FUEL_CARD_PRIV must not fire when the employee is on a mobility budget: "
                "the fuel card fields are meaningless/hidden in that mode.")

    def test_fuel_card_personal_use_ignored_without_fuel_card(self):
        with freeze_time('2026-01-20'):
            employee = self.create_employee({
                'name': 'Fuel Card Private Use employee no fuel card',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'fuel_card': 0.0,
                'fuel_card_personal_use': 50.0,
            })
            version = employee.version_id

            slip = self.env['hr.payslip'].create({
                'name': f"Payslip {employee.name} 2026-01",
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': version.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            slip.compute_sheet()

            line = slip.line_ids.filtered(lambda l: l.code == 'FUEL_CARD_PRIV')
            self.assertFalse(
                line,
                "FUEL_CARD_PRIV must not fire when fuel_card is 0: a stale "
                "fuel_card_personal_use value shouldn't leak in once the fuel card itself is removed.")

    def test_fuel_card_personal_use_manual_override_survives_recompute(self):
        with freeze_time('2026-01-20'):
            employee = self.create_employee({
                'name': 'Fuel Card Private Use employee manual override',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'fuel_card': 150.0,
                'fuel_card_personal_use': 50.0,
            })
            version = employee.version_id

            slip = self.env['hr.payslip'].create({
                'name': f"Payslip {employee.name} 2026-01",
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'version_id': version.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            })
            slip.compute_sheet()
            slip.input_line_ids.filtered(lambda l: l.code == 'FUEL_CARD_PRIV').amount = 80.0
            slip.compute_sheet()

            line = slip.line_ids.filtered(lambda l: l.code == 'FUEL_CARD_PRIV')
            self.assertEqual(
                line.total, 80.0,
                "A manually-overridden salary input value on the payslip should survive a "
                "compute_sheet() recompute rather than being reset to the employee's default.")
