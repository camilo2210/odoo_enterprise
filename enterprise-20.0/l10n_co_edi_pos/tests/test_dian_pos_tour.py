from unittest.mock import patch

from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged

from .common import TestL10nCoEdiPosCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericCOEdiPos(TestGenericLocalization, TestL10nCoEdiPosCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pos_config = cls.main_pos_config
        company = pos_config.company_id

        company.name = 'Company CO'
        cls.partner_a = cls.env.ref('l10n_co_edi.consumidor_final_customer')
        cls.partner_a.name = "AAAA Generic Partner"

        cash_pm = pos_config.payment_method_ids.filtered(lambda p: p.type == 'cash')
        bank_pm = pos_config.payment_method_ids - cash_pm
        pos_config.payment_method_ids = bank_pm + cash_pm[0]

        for payment_method in pos_config.payment_method_ids:
            payment_method.l10n_co_edi_pos_payment_option_id = cls.default_pos_payment_option

        default_unspsc = cls.env['product.unspsc.code'].search([('code', '=', '01010101')], limit=1)
        cls.whiteboard_pen.unspsc_code_id = default_unspsc
        cls.wall_shelf.unspsc_code_id = default_unspsc

        pos_config.l10n_co_edi_pos_serial_number = "SN000001"
        pos_config.l10n_co_edi_final_consumer_invoices_journal_id.write({
            'l10n_co_edi_pos_is_final_consumer': True,
        })
        pos_config.l10n_co_edi_final_consumer_invoices_journal_id.l10n_co_edi_pos_sequence_id.update({
            'number_next': 990000001,
            'prefix': "SETF",
        })

    def test_generic_localization(self):
        with (
            patch(f'{self.utils_path}._build_and_send_request') as mock_request,
            self._disable_get_acquirer_call(),
            self._mock_get_status(),
        ):
            mock_request.side_effect = [
                self._mocked_response('SendBillSync_warnings.xml', 200),
                self._mocked_response('GetStatusZip_warnings.xml', 200),
            ]

            super().test_generic_localization()
        report_data = self.env['report.point_of_sale.report_saledetails'].get_sale_details(session_ids=[self.main_pos_config.current_session_id.id])
        self.assertEqual(report_data['l10n_co_edi_pos_serial_number'], 'SN000001', "Serial number should be correctly passed to the report data")

    def test_co_pos_refund(self):
        self.main_pos_config.open_ui()
        with (
            patch(f'{self.utils_path}._build_and_send_request') as mock_request,
            self._disable_get_acquirer_call(),
            self._mock_get_status(),
        ):
            mock_request.side_effect = [
                self._mocked_response('SendBillSync_warnings.xml', 200),
                self._mocked_response('SendBillSync_warnings.xml', 200),
            ]
            self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, 'test_co_pos_refund', login="accountman")
