from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrPayslip(TransactionCase):

    def setUp(self):
        super().setUp()

        self.company_hk = self.env['res.company'].create({
            'name': 'HK Co',
            'country_id': self.env.ref('base.hk').id,
        })

        self.employee_hk = self.env['hr.employee'].create({
            'name': 'HK Employee',
            'company_id': self.company_hk.id,
        })

    def test_remove_payslip_period(self):
        """Test payroll computations when the payslip period is removed."""
        slip_form = Form(self.env['hr.payslip'].with_company(self.company_hk))
        slip_form.date_from = False

        self.assertEqual(slip_form.l10n_hk_average_daily_wage, 0.0)

    def test_payslip_without_version_contract_date_start(self):
        """
        Test creating a payslip for an employee whose version
        has no contract start date.
        """
        self.assertFalse(self.employee_hk.version_id.contract_date_start)

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee_hk.id,
        })

        self.assertIn('No running contract', [issue['message'] for issue in payslip.issues.values()])
