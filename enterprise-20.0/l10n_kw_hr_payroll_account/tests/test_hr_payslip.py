# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setup_armageddon_tax(cls, tax_name, company_data):
        kw_country_id = cls.env.ref('base.kw').id
        if not cls.env['account.tax.group'].search([('country_id', '=', kw_country_id)], limit=1):
            cls.env['account.tax.group'].create({
                'name': 'Dummy Kuwait Tax Group',
                'country_id': kw_country_id,
                'sequence': 1,
            })
        return super().setup_armageddon_tax(tax_name, company_data)

    @classmethod
    @TestPayslipValidationCommon.setup_country('kw')
    def setUpClass(cls):
        super().setUpClass()

        cls._setup_common(
            country=cls.env.ref('base.kw'),
            structure=cls.env.ref('l10n_kw_hr_payroll.l10n_kw_monthly_pay'),
            structure_type=cls.env.ref('l10n_kw_hr_payroll.l10n_kw_employee'),
            resource_calendar=cls.env.ref('l10n_kw_hr_payroll.l10n_kw_resource_calendar_std_40h'),
            tz='Asia/Kuwait',
        )

        cls.kuwait_employee = cls.env['hr.employee'].create({
            'name': 'Kuwait Employee',
            'company_id': cls.env.company.id,
            'wage': 1550.0,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
        })

    def test_kuwait_payslip(self):
        version = self.kuwait_employee._get_version(date=date(2025, 1, 1))
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31), version_id=version.id, employee_id=self.kuwait_employee.id)
        payslip_results = {
            'BASIC': 1550.0,
            'GROSS': 1550.0,
            'KW_SS_BASIC_EMP': -155.0,
            'KW_SS_BASIC_COMP': 232.5,
            'KW_SS_UNEMP_EMP': -7.75,
            'KW_SS_UNEMP_COMP': 7.75,
            'EOS_PROV': 129.167,
            'LEAVE_PROV': 176.136,
            'NET': 1387.25,
            'NET_COST': 1790.25,
        }
        self._validate_payslip(payslip, payslip_results)
