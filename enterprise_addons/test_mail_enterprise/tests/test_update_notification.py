# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.test_base.tests.test_tools.test_cloc import TestClocCustomization

from ast import literal_eval


class TestClocICP(TestClocCustomization):

    def create_field(self, name):
        # install_mode avoids StudioMixin tagging the field as Studio-generated
        # if web_studio happens to be installed, which would make cloc exclude it.
        env = self.env
        self.env = env(context={**env.context, 'install_mode': True})
        try:
            return super().create_field(name)
        finally:
            self.env = env

    def test_check_cloc_result_in_icp(self):
        self.create_field('x_invoice_count')
        message = self.env["publisher_warranty.contract"]._get_message()
        self.assertTrue('maintenance' in message)
        store_cloc = self.env["ir.config_parameter"].get_str('publisher_warranty.cloc')
        self.assertEqual(literal_eval(store_cloc)['modules']['odoo/studio'], 1)
