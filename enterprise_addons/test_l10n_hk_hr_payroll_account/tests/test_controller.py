# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEmpfController(TestL10NHkHrPayrollAccountCommon, HttpCase):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_hk_eoy_pay_month = False

    def test_download_controller(self):
        """
        Test downloading the empf file using the controller endpoint.
        We will ensure that the controller works and return the same content as the reports content we stored in Odoo.
        """
        self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2021, 12, 1),
                'contract_date_start': date(2021, 12, 1),
                'wage': 20000.0,
                'l10n_hk_mpf_scheme_id': self.mpf_scheme.id,
                'l10n_hk_mpf_registration_status': 'next_contribution',
                'l10n_hk_mpf_contribution_start': 'at_due_date',
                'l10n_hk_mpf_scheme_join_date': date(2021, 12, 1),
                'identification_id': 'Z683365A',
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'private_phone': '98651234',
                'private_email': 'defghi@address.ik',
                'birthday': date(2002, 2, 2),
                'l10n_hk_surname': 'AU-YEUNG',
                'l10n_hk_given_name': 'FUNG',
                'l10n_hk_name_in_chinese': '歐陽 峰',
                'sex': 'male',
            }
        )

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        action_url = report.action_generate_report()['url']
        self.authenticate("admin", "admin")
        res = self.url_open(action_url)
        self.assertEqual(res.content, self._get_csv_reports_per_type(report, 'new_employees').raw.content)
