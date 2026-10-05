from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericAT(TestGenericLocalization):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('at')
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.l10n_at_cash_regid = "ATU12345678"

    def test_generic_localization(self):
        order, html = super().test_generic_localization()
        self.assertTrue(f"Fiskaly Register ID: {order.config_id.l10n_at_cash_regid}" in html)
        self.assertTrue("Sicherheitseinrichtung ausgefallen" in html)
