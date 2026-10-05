# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrPayslip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.struct_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'US YTD structure type',
        })
        cls.struct = cls.env['hr.payroll.structure'].create({
            'name': 'US YTD structure',
            'type_id': cls.struct_type.id,
            'ytd_computation': True,
        })
        cls.us_company = cls.env['res.company'].create({
            'name': 'US Company',
            'country_id': cls.env.ref('base.us').id,
            'ytd_reset_month': '1',
            'ytd_reset_day': 1,
        })
        cls.employee = cls._create_employee(cls.us_company)
        cls.version = cls.employee.version_id

    @classmethod
    def _create_employee(cls, company):
        return cls.env['hr.employee'].create({
            'name': 'YTD employee',
            'company_id': company.id,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'wage': 5000,
            'structure_type_id': cls.struct_type.id,
        })

    def _make_slip(self, date_from, date_to, state='draft', paid_date=False):
        employee = self.employee
        slip = self.env['hr.payslip'].with_context(default_date_to=date_to).create({
            'name': 'slip %s' % date_from,
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'company_id': employee.company_id.id,
            'struct_id': self.struct.id,
            'date_from': date_from,
        })
        self.assertEqual(slip.date_to, date_to)
        vals = {'state': state}
        if paid_date:
            vals['paid_date'] = paid_date
        slip.write(vals)
        return slip

    def test_reference_date_is_paid_date(self):
        """ In the US the YTD reference date is the payment date. """
        slip = self._make_slip(
            date(2026, 3, 1), date(2026, 3, 31), paid_date=date(2026, 4, 2))
        self.assertEqual(slip._get_ytd_reference_date(), date(2026, 4, 2),
            "A slip should bucket by its payment date")

    def test_reference_date_defaults_to_close_date(self):
        """ Without a payment date, a US payslip is computed on its close date
        and warns the user about it.
        """
        slip = self._make_slip(date(2026, 3, 1), date(2026, 3, 31))
        slip.compute_sheet()
        self.assertEqual(slip._get_ytd_reference_date(), date(2026, 3, 31),
            "A slip without a payment date should bucket by its close date")
        self.assertTrue(
            any('03/31/2026' in issue['message'] for issue in (slip.issues or {}).values()),
            "A slip without a payment date should warn about the fallback date")

        slip.paid_date = date(2026, 4, 2)
        self.assertFalse(
            any('03/31/2026' in issue['message'] for issue in (slip.issues or {}).values()),
            "Setting the payment date should drop the warning")

    def test_december_slip_paid_in_january(self):
        """ A December payslip paid in January should count towards the following year."""
        dec_slip = self._make_slip(
            date(2025, 12, 16), date(2025, 12, 29), 'paid', paid_date=date(2026, 1, 2))
        jan_slip = self._make_slip(date(2026, 1, 1), date(2026, 1, 15), paid_date=date(2026, 1, 16))

        last_ytd = jan_slip._get_last_ytd_payslips()
        self.assertEqual(last_ytd[jan_slip], dec_slip,
            "A December slip paid in January should feed the January slip's YTD")

    def test_slip_paid_in_its_own_year(self):
        """ A payslip created and paid in the same period counts towards the same year."""
        self._make_slip(
            date(2025, 11, 1), date(2025, 11, 30), 'paid', paid_date=date(2025, 11, 30))
        jan_slip = self._make_slip(date(2026, 1, 1), date(2026, 1, 15), paid_date=date(2026, 1, 16))

        last_ytd = jan_slip._get_last_ytd_payslips()
        self.assertFalse(last_ytd.get(jan_slip),
            "A slip paid in the previous year must not count toward the new year's YTD")

    def test_us_payslip_validation_stamps_close_date(self):
        """ Validating a US payslip without payment date defaults to closing date."""
        slip = self._make_slip(date(2026, 5, 1), date(2026, 5, 31))
        slip.action_payslip_done()
        self.assertEqual(slip.state, 'validated')
        self.assertEqual(slip.paid_date, date(2026, 5, 31),
            "A slip validated without a payment date should be stamped with its close date")

    def test_us_payslip_validation_keeps_paid_date(self):
        """ A payment date set should not be overwritten upon validation."""
        slip = self._make_slip(
            date(2026, 5, 1), date(2026, 5, 31), paid_date=date(2026, 6, 1))
        slip.action_payslip_done()
        self.assertEqual(slip.paid_date, date(2026, 6, 1),
            "Validating a slip should not overwrite its payment date")
