# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.addons.l10n_ke_edi_oscu.tests.common import TestKeEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestKeEdiInvoiceSequence(TestKeEdiCommon):
    """ The eTIMS invoice number is only given back to the sequence when the failing
        call is the one that took it. """

    @classmethod
    @TestKeEdiCommon.setup_country('ke')
    def setUpClass(cls):
        super().setUpClass()

    def _patch_etims(self, **answers):
        """ Make `_l10n_ke_call_etims` answer with the given (error, data) per endpoint. """
        def _call_etims(company, endpoint, content):
            error, data = answers.get(endpoint, ({'code': '001'}, {}))
            return error, data, None

        return patch(
            'odoo.addons.l10n_ke_edi_oscu.models.res_company.ResCompany._l10n_ke_call_etims',
            side_effect=_call_etims, autospec=True,
        )

    def _post_invoice(self):
        invoice = self.init_invoice(
            'out_invoice',
            partner=self.partner_a,
            invoice_date='2024-01-28',
            products=[self.product_service],
        )
        invoice.action_post()
        return invoice

    @mute_logger('odoo.addons.l10n_ke_edi_oscu.models.account_move')
    def test_send_invoice_rejected(self):
        invoice = self._post_invoice()

        with self._patch_etims(saveTrnsSalesOsdc=({'code': '894'}, {})):
            invoice._l10n_ke_oscu_send_customer_invoice()

        self.assertFalse(invoice.l10n_ke_oscu_invoice_number)
        self.assertEqual(invoice._l10n_ke_get_invoice_sequence().number_next, 1)

    @mute_logger('odoo.addons.l10n_ke_edi_oscu.models.account_move')
    def test_send_invoice_timeout(self):
        invoice = self._post_invoice()

        with self._patch_etims(saveTrnsSalesOsdc=({'code': 'TIM'}, {})):
            invoice._l10n_ke_oscu_send_customer_invoice()

        self.assertEqual(invoice.l10n_ke_oscu_invoice_number, 1)
        self.assertEqual(invoice._l10n_ke_get_invoice_sequence().number_next, 2)

    @mute_logger('odoo.addons.l10n_ke_edi_oscu.models.account_move')
    def test_send_invoice_rejected_after_timeout(self):
        """ The retry reuses the number kept from the timeout instead of taking a
            new one, so failing must not move the sequence back onto a number
            another invoice already holds. """
        timed_out = self._post_invoice()
        with self._patch_etims(saveTrnsSalesOsdc=({'code': 'TIM'}, {})):
            timed_out._l10n_ke_oscu_send_customer_invoice()

        self.assertEqual(timed_out.l10n_ke_oscu_invoice_number, 1)

        other = self._post_invoice()
        with self._patch_etims(saveTrnsSalesOsdc=({'code': 'TIM'}, {})):
            other._l10n_ke_oscu_send_customer_invoice()

        self.assertEqual(other.l10n_ke_oscu_invoice_number, 2)

        with self._patch_etims(
            selectInvoiceDetails=({'code': '001'}, {}),
            saveTrnsSalesOsdc=({'code': '894'}, {}),
        ):
            timed_out._l10n_ke_oscu_send_customer_invoice()

        self.assertFalse(timed_out.l10n_ke_oscu_invoice_number)
        self.assertEqual(timed_out._l10n_ke_get_invoice_sequence().number_next, 3)
