import json
import re
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import BinaryBytes, mute_logger

from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import _get_nilvera_client

NILVERA_REQUEST = 'odoo.addons.l10n_tr_nilvera.lib.nilvera_client.NilveraClient.request'
UUID = "11111111-2222-3333-4444-555555555555"
# The answer-status payload Nilvera returns per UUID, and the state it must map to.
STATUS_CASES = {
    UUID: ({'Answer': {'AnswerCode': 'acceptAll'}}, 'accepted'),
    'uuid_no_answer_yet': ({'Answer': None}, 'waiting'),
    'uuid_unhandled_answer': ({'Answer': {'AnswerCode': 'something_new'}}, 'error'),
}


def _nilvera_request(method, endpoint, *args, **kwargs):
    if match := re.fullmatch(r'/edespatch/Purchase/([\w-]+)/Status', endpoint):
        return STATUS_CASES[match[1]][0]
    if match := re.fullmatch(r'/edespatch/Purchase/Answer/[\w-]+/(xml|pdf)', endpoint):
        return "<ReceiptAdvice/>" if match[1] == 'xml' else "cGRmLWJ5dGVz"
    return MagicMock(status_code=200, **{'json.return_value': {}})


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestDispatchResponse(TransactionCase):
    """A TR receipt with a dispatch UUID, its XML and a to-do unit_count check."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': "TR Response Co", 'country_id': cls.env.ref('base.tr').id})
        cls.env.user.company_ids |= cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_id = cls.company
        warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.picking_type_in, cls.picking_type_out = warehouse.in_type_id, warehouse.out_type_id
        # quality.point.team_id is required and its default raises for a company without a team, as here.
        cls.team = cls.env['quality.alert.team'].create({'name': "TR Quality Team", 'company_id': cls.company.id})
        cls.product_a, cls.product_b = cls.env['product.product'].create([
            {'name': "Product A", 'type': 'consu', 'is_storable': True},
            {'name': "Product B", 'type': 'consu', 'is_storable': True},
        ])
        cls.point = cls._create_point()
        cls.picking = cls.env['stock.picking'].create({
            'picking_type_id': cls.picking_type_in.id, 'company_id': cls.company.id,
            'move_ids': [Command.create({'product_id': cls.product_a.id, 'product_uom_qty': 10.0})],
        })
        cls.picking.l10n_tr_nilvera_uuid = UUID
        cls.picking.l10n_tr_nilvera_edispatch_xml_file = BinaryBytes(b"<DespatchAdvice/>")
        cls.check = cls.env['quality.check'].create({
            'picking_id': cls.picking.id, 'company_id': cls.company.id, 'team_id': cls.team.id, 'point_id': cls.point.id,
        })
        cls.line = cls.check.l10n_tr_response_line_ids

    @classmethod
    def _create_point(cls, **kwargs):
        return cls.env['quality.point'].create({
            'title': "Unit Count Point", 'company_id': cls.company.id, 'team_id': cls.team.id,
            'picking_type_ids': [Command.set(cls.picking_type_in.ids)], 'measure_on': 'operation',
            'test_type_id': cls.env.ref('l10n_tr_nilvera_edispatch_quality.test_type_unit_count').id, **kwargs,
        })

    def _qty(self, value):
        return {'UnitCode': 'C62', 'Value': value}

    def test_unit_count_point_setup_rules(self):
        non_tr = self.env['res.company'].create({'name': "BE Co", 'country_id': self.env.ref('base.be').id})
        non_tr_team = self.env['quality.alert.team'].create({'name': "BE Team", 'company_id': non_tr.id})
        for kwargs in (
            {'picking_type_ids': [Command.set(self.picking_type_out.ids)]},
            {'measure_on': 'product'},
            {'company_id': non_tr.id, 'team_id': non_tr_team.id},
        ):
            with self.assertRaises(ValidationError):
                self._create_point(**kwargs)

    def test_the_count_derives_the_answer(self):
        self.env['ir.sequence'].search([('code', '=', 'quality.point')], limit=1).prefix = 'ABC'
        self.check.name = "QCHK/00042"
        # 10 ordered, 12 arrived, 4 sent back: 6 kept, 2 unordered, nothing missing.
        self.line.write({'received_qty': 12.0, 'rejected_qty': 4.0, 'rejection_reason': "Crushed boxes"})
        self.assertRecordValues(self.line, [{'accepted_qty': 6.0, 'missing_qty': 0.0, 'excess_qty': 2.0}])
        values = self.picking._l10n_tr_get_dispatch_response_values()
        self.assertEqual(values['DespatchUUID'], UUID)
        self.assertEqual(values['Serie'], f"ABC{self.picking.scheduled_date.year}000000042")
        self.assertEqual(values['Notes'], ["Crushed boxes"])
        self.assertNotIn('AcceptAll', values)
        answer_line, = values['DespatchAnswerLines']
        # A move answering no purchase carries no price at all rather than a price of zero.
        self.assertEqual(answer_line, {
            'Index': 0,
            'Received': self._qty(12.0), 'Short': self._qty(0.0),
            'Rejected': self._qty(4.0), 'Oversupply': self._qty(2.0),
            'RejectReason': "Crushed boxes", 'Name': "Product A",
            'Description': self.line.move_id.description_picking,
        })
        # A delivery that arrived complete is answered as a whole instead.
        self.line.write({'received_qty': 10.0, 'rejected_qty': 0.0})
        self.assertTrue(self.picking._l10n_tr_get_dispatch_response_values()['AcceptAll'])
        for vals in (
            {'rejected_qty': 11.0},                            # more sent back than arrived
            {'rejected_qty': 2.0, 'rejection_reason': False},   # nothing said about why
        ):
            with self.assertRaises(ValidationError):
                self.line.write(vals)

    def test_the_wizard_writes_the_count_onto_the_receipt(self):
        action = self.check.action_open_quality_check_wizard()
        form = Form(self.env['quality.check.wizard'].with_context(**action['context']))
        with form.l10n_tr_count_line_ids.edit(0) as counted:
            counted.received_qty = 7.0
        form.save().do_pass()
        # What the operator typed reaches the answer line, and the move it was counted on.
        self.assertEqual(self.check.quality_state, 'pass')
        self.assertEqual(self.line.received_qty, 7.0)
        self.assertEqual(self.picking.move_ids.quantity, 7.0)
        # An answered count is the record of what was answered, whatever the receipt does next.
        self.line.move_id.product_uom_qty = 25.0
        self.picking.write({'move_ids': [Command.create({'product_id': self.product_b.id, 'product_uom_qty': 5.0})]})
        self.assertRecordValues(self.line, [{'product_uom_qty': 10.0, 'missing_qty': 3.0}])
        self.assertEqual(self.check.l10n_tr_response_line_ids, self.line)

    @mute_logger('odoo.addons.l10n_tr_nilvera_edispatch_quality.models.stock_picking')
    def test_the_answer_is_sent_and_followed_up(self):
        self.assertFalse(self.picking.l10n_tr_nilvera_response_ready)
        self.line.received_qty = 10.0
        self.check.do_pass()
        self.assertTrue(self.picking.l10n_tr_nilvera_response_ready)
        with patch(NILVERA_REQUEST, side_effect=_nilvera_request) as request:
            self.picking.action_l10n_tr_send_dispatch_response()
            self.assertEqual(self.picking.l10n_tr_nilvera_response_status, 'sent')
            payload = self.picking.l10n_tr_nilvera_response_json_id
            request.assert_called_once_with('POST', endpoint='/edespatch/Purchase/SendAnswer',
                                            json=json.loads(payload.raw.content), handle_response=False)
            self.assertIn(payload, self.picking._get_mail_thread_data_attachments())
            # An answer that went through closes the receipt; the cron follows it up from there.
            self.assertFalse(self.picking.l10n_tr_nilvera_response_ready)
            for uuid, (_payload, expected) in STATUS_CASES.items():
                self.picking.l10n_tr_nilvera_uuid = uuid
                with _get_nilvera_client(self.env._, self.company) as client:
                    self.picking._l10n_tr_nilvera_sync_response_status(client)
                self.assertEqual(self.picking.l10n_tr_nilvera_response_status, expected)
        # Settling pulls the signed documents Nilvera holds onto the receipt.
        self.assertIn(self.picking.l10n_tr_nilvera_response_pdf_id, self.picking._get_mail_thread_data_attachments())
