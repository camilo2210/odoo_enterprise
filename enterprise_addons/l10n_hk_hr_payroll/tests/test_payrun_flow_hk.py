# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.test_payrun_flow import TestPayrunFlow


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestPayrunFlowHK(TestPayrunFlow):
    def test_branch_company_selection_payrun_hk(self):
        self._setup_for_branch_company_selection(self.env.ref('base.hk').id)
        self.start_tour("/odoo", 'branch_company_selection_payrun_tour', login="admin")
