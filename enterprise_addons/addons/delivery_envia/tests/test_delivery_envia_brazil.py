from odoo import Command
from odoo.tests import tagged
from odoo.tools import BinaryBytes, file_open

from odoo.addons.delivery_envia.tests.test_delivery_envia import TestDeliveryEnvia, _mock_envia_call


@tagged('post_install', '-at_install')
class TestDeliveryEnviaBrazil(TestDeliveryEnvia):
    """Goods leaving Brazil may only travel with the NF-e covering them on the label."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if cls.env['ir.module.module']._get('l10n_br_edi_stock').state != 'installed':
            cls.skipTest(cls, "This class requires l10n_br_edi_stock to be installed")

        cls.your_company.write({
            'name': 'Odoo BR',
            'country_id': cls.env.ref('base.br').id,
            'street': 'Praça Mauá 1',
            'street2': 'Centro',
            'state_id': cls.env.ref('base.state_br_rj').id,
            'city': 'Rio de Janeiro',
            'zip': '20081-240',
            'phone': '+55 11 96123-4567',
        })
        cls.avatax_fp = cls.env['account.fiscal.position'].create({
            'name': 'Avatax Brazil',
            'l10n_br_is_avatax': True,
        })

    def _create_nfe(self, status, fiscal_position=None):
        """Create the posted NF-e a transfer references, with `status` as SEFAZ's answer."""
        nfe = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.br_partner.id,
            'invoice_date': '2026-04-06',
            'fiscal_position_id': (fiscal_position or self.avatax_fp).id,
            'invoice_line_ids': [Command.create({'product_id': self.product_to_ship1.id})],
        })
        nfe.journal_id.l10n_br_invoice_serial = '1'
        nfe.action_post()
        nfe.write({
            'l10n_br_last_edi_status': status,
            'l10n_br_access_key': '35260412345678000195550010000012341123456789',
        })
        return nfe

    def _ship_referencing(self, nfe, payloads=None):
        """Ship a sale order through Envia with `nfe` referenced on its transfer."""
        sale_order = self.env['sale.order'].create({
            'partner_id': self.br_partner.id,
            'order_line': [Command.create({'product_id': self.product_to_ship1.id})],
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.envia.id,
            'order_id': sale_order.id,
        })

        def capture(endpoint, payload):
            if endpoint == 'ship/generate':
                payloads.append(payload)

        with _mock_envia_call(capture if payloads is not None else None):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order.action_confirm()

            picking = sale_order.picking_ids[0]
            picking.l10n_br_related_move_id = nfe
            picking.action_assign()
            picking.move_ids.picked = True
            picking._action_done()

        return picking

    def test_nfe_sent_with_label_request(self):
        payloads = []
        nfe = self._create_nfe('accepted')
        with file_open('l10n_br_edi/tests/NFe4124030.xml', 'rb') as xml_file:
            nfe.l10n_br_edi_xml_attachment_file = BinaryBytes(xml_file.read())

        picking = self._ship_referencing(nfe, payloads)

        self.assertEqual(picking.carrier_tracking_ref, "1Z48746Q48746", "The label should have been requested.")
        self.assertEqual(
            payloads[0]['packages'][0]['xmlData'],
            [{
                'documentType': 'nfe',
                'nfeKey': '35260412345678000195550010000012341123456789',
                'nfeNumber': '1234',
                'nfeSerie': '1',
                'nfeDate': '2024-03-07T20:13:19-03:00',
            }],
            "The NF-e covering the goods should be sent with the parcel, read from its authorized XML.",
        )

    def test_no_label_until_the_nfe_is_accepted(self):
        payloads = []
        nfe = self._create_nfe('pending')

        picking = self._ship_referencing(nfe)

        self.assertEqual(picking.state, 'done', "Waiting on SEFAZ should not hold the transfer back.")
        self.assertFalse(
            picking.carrier_tracking_ref,
            "No label should be requested while the NF-e is not accepted, as it can only be requested once.",
        )

        nfe.l10n_br_last_edi_status = 'accepted'
        with _mock_envia_call(lambda endpoint, payload: endpoint == 'ship/generate' and payloads.append(payload)):
            picking.send_to_shipper()

        self.assertEqual(
            picking.carrier_tracking_ref, "1Z48746Q48746", "The label should be requested once the NF-e is accepted.",
        )
        self.assertIsNone(
            payloads[0]['packages'][0]['xmlData'][0]['nfeDate'],
            "Without the authorized XML there is no emission instant to send, the invoice date has no time.",
        )
