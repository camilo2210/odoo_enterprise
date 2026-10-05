# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.l10n_in_reports.tests.common import L10nInTestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEdiIrnNumber(L10nInTestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_l10n_in_edi_send_invoice_stores_irn_number(self):
        self.default_company.l10n_in_edi_feature = True
        self.partner_a.l10n_in_gst_treatment = 'regular'
        invoice = self._create_invoice_one_line(
            partner_id=self.partner_a,
            product_id=self.product_a,
            tax_ids=self.comp_igst_18,
            post=True)
        self.assertEqual(invoice.l10n_in_edi_status, 'to_send')
        response_data = {'Irn': '58B1616C8A98D62163A6214A5C8234017E8A91B5C705F0C39C717B4B3846690B', 'AckNo': 'ACK-001'}
        with patch.object(self.env.registry['account.move'], '_l10n_in_edi_connect_to_server', return_value={'data': response_data}):
            invoice._l10n_in_edi_send_invoice()
        self.assertEqual(invoice.l10n_in_edi_status, 'sent')
        self.assertEqual(invoice.l10n_in_irn_number, response_data['Irn'].lower())
