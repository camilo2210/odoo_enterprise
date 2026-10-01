# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_payroll.tests.common import TestPayrollBase


class TestPayrollCommon(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({
            'country_id': cls.env.ref('base.om').id,
            'currency_id': cls.env.ref('base.OMR').id,
        })
        cls.company = cls.env.company
        cls._setup_common(
            country=cls.env.ref('base.om'),
            structure=cls.env.ref('l10n_om_hr_payroll.l10n_om_monthly_pay'),
            structure_type=cls.env.ref('l10n_om_hr_payroll.l10n_om_employee'),
            resource_calendar=cls.env.ref('l10n_om_hr_payroll.l10n_om_resource_calendar_def_40h'),
            tz='Asia/Muscat',
        )
