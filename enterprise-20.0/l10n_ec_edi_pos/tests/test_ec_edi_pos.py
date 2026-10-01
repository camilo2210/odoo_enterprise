from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericECEdi(TestGenericLocalization):

    _pos_partner_pos_form_fields = ['vat', 'additional_identifiers']
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ec')
    def setUpClass(cls):
        super().setUpClass()
