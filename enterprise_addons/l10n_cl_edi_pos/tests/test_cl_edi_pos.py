from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericCL(TestGenericLocalization):

    _pos_partner_pos_form_fields = ['vat', 'additional_identifiers', 'l10n_cl_sii_taxpayer_type']
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('cl')
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.company_id.name = 'Company CL'
        cls.main_pos_config.company_id.l10n_cl_dte_resolution_date = '2020-01-01'

    def test_generic_localization(self):
        order, html = super().test_generic_localization()
        self.assertTrue(order.account_move.l10n_latam_document_number in html)
        self.assertTrue(order.account_move.l10n_latam_document_type_id.name in html)
        self.assertTrue("RUT" in html)
        self.assertTrue("Verifique documento en www.sii.cl" in html)
