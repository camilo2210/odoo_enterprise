from contextlib import contextmanager
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.tools import misc

from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class TestUyEdiPosCommon(TestUyEdi, TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_uy.l10n_uy_edi_ucfe_env = "demo"

        cls.config = cls.basic_config
        cls.config.journal_id = cls.company_data["default_journal_sale"]

        cls.product_22 = cls.env["product.product"].create({
            "name": "POS Product (VAT 22)",
            "available_in_pos": True,
            "list_price": 100.0,
            "taxes_id": [Command.set(cls.tax_22.ids)],
            "company_id": cls.company_uy.id,
        })

        cls.cash_pm = cls.config.payment_method_ids.filtered(lambda pm: pm.type == "cash")[:1]

        cls.mocked_pos_cfes_path = "l10n_uy_edi_pos/tests/expected_cfes/"

    @contextmanager
    def _pos_session(self):
        session = self.open_new_session(0.0)
        yield session
        total_cash = sum(
            session.order_ids.payment_ids.filtered(
                lambda payment: payment.payment_method_id == self.cash_pm
            ).mapped("amount")
        )
        session.close_session_from_ui({self.cash_pm.id: total_cash})

    def _refund_order(self, original):
        """ Create, pay and send a refund of ``original`` through the real POS refund mechanism. """
        with freeze_time(self.frozen_today, tz_offset=3):
            refund = original._refund()
            make_payment = self.env["pos.make.payment"].with_context(
                active_ids=[refund.id], active_id=refund.id,
            ).create({
                "payment_method_id": self.cash_pm.id,
                "amount": refund.amount_total,
            })
            make_payment.check()
            refund.l10n_uy_edi_action_send_document()
        return refund

    def _create_order(self, ui_data, extra_data=None):
        with freeze_time(self.frozen_today, tz_offset=3):
            order_data = self.create_ui_order_data(**ui_data)
            if extra_data:
                order_data |= extra_data
            results = self.env["pos.order"].sync_from_ui([order_data])
        return self.env["pos.order"].browse(results["pos.order"][0]["id"])

    def _check_pos_cfe(self, order, expected_xml_file):
        """ Demo-mode POS CFE assertion, like l10n_uy_edi._check_cfe """
        doc = order.l10n_uy_edi_document_id
        self.assertTrue(doc.pos_order_id, "The CFE is expected on the order itself")
        self.assertEqual(order.l10n_uy_edi_document_number, "DE%07d" % order.id, "Not a valid CFE number")
        self.assertEqual(order.l10n_uy_edi_cfe_state, "accepted", "CFE should be accepted in demo mode")

        expected_xml = self.get_xml_tree_from_string(
            misc.file_open(self.mocked_pos_cfes_path + expected_xml_file + ".xml").read(),
        )
        result_xml = self.get_xml_tree_from_attachment(doc.attachment_id)

        # Credit notes reference the original order's dynamic serie/number, patch it in.
        if order.refunded_order_id:
            original_doc = order.refunded_order_id.l10n_uy_edi_document_id
            ref_number = order.l10n_uy_edi_document_id._get_doc_parts(original_doc)[1]
            namespace = {"cfe": "http://cfe.dgi.gub.uy"}
            expected_xml.find(".//cfe:Referencia/cfe:Referencia/cfe:NroCFERef", namespace).text = ref_number

        self.assertXmlTreeEqual(expected_xml, result_xml)

    @contextmanager
    def _mock_pos_inbox(self, response_file, exception=None):
        """ Mock the Uruware inbox (send) and query (legal PDF) calls for the non-demo tests. """
        with (
            patch(
                f"{self.utils_path}._ucfe_inbox",
                return_value=self._mocked_response(response_file, exception=exception),
            ),
            patch(f"{self.utils_path}._ucfe_query", return_value=self._mocked_response(False)),
        ):
            yield
