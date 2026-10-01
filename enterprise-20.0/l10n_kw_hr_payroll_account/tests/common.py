# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_payroll.tests.common import TestPayrollBase


class TestPayrollCommon(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({
            'country_id': cls.env.ref('base.kw').id,
            'currency_id': cls.env.ref('base.KWD').id,
        })
        cls.company = cls.env.company
        cls._setup_common(
            country=cls.env.ref('base.kw'),
            structure=cls.env.ref('l10n_kw_hr_payroll.l10n_kw_monthly_pay'),
            structure_type=cls.env.ref('l10n_kw_hr_payroll.l10n_kw_employee'),
            resource_calendar=cls.env.ref('l10n_kw_hr_payroll.l10n_kw_resource_calendar_std_40h'),
            tz='Asia/Kuwait',
        )
