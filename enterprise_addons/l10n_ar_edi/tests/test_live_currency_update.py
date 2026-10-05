from odoo.tests import tagged
from odoo.addons.l10n_ar_edi.tests.common import TestArEdiCommon


@tagged('-at_install', 'post_install', '-standard', 'external', 'external_l10n')
class CurrencyLiveUpdate(TestArEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestArEdiCommon.setup_afip_ws('wsfe')
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_usd.active = True

    def test_live_currency_update_arca(self):
        self.company_ri.currency_provider = 'arca'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.company_ri.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)
