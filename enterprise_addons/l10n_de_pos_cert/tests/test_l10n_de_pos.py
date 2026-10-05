from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericDE(TestGenericLocalization):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('de')
    def setUpClass(cls):
        super().setUpClass()

    def test_generic_localization(self):
        _, html = super().test_generic_localization()
        self.assertTrue("This is a TEST receipt. Go to your company settings to be in a production environment." in html)
