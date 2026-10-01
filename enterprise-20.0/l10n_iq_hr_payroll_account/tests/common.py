# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_payroll.tests.common import TestPayrollBase


class TestPayrollCommon(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({
            'country_id': cls.env.ref('base.iq').id,
            'currency_id': cls.env.ref('base.IQD').id,
        })
        cls.company = cls.env.company
        cls._setup_common(
            country=cls.env.ref('base.iq'),
            structure=cls.env.ref('l10n_iq_hr_payroll.l10n_iq_regular_pay'),
            structure_type=cls.env.ref('l10n_iq_hr_payroll.l10n_iq_employee'),
            resource_calendar=cls.env.ref('l10n_iq_hr_payroll.l10n_iq_resource_calendar'),
            tz='Asia/Baghdad',
        )
