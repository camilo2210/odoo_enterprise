from ast import literal_eval

from odoo.tests import Form

from .common import TestVoipSaleCommon


class TestVoipCall(TestVoipSaleCommon):

    def test_action_view_sale_orders_uses_commercial_partner(self):
        """Smart button should show sale orders from the whole partner family (commercial partner).
        New records should default to the call's partner, not the commercial partner."""
        call = self.env["voip.call"].create({
            "partner_id": self.child_partner.id,
            "phone_number": "+1234567891",
            "user_id": self.sale_manager.id,
        })
        self.assertEqual(call.commercial_partner_sale_order_count, self.parent_partner.sale_order_count)
        action = call.action_view_sale_orders()
        orders = self.env["sale.order"].search(action["domain"])
        self.assertEqual(len(orders), call.commercial_partner_sale_order_count)
        self.assertEqual(action["context"]["default_partner_id"], self.child_partner.id)

    def test_action_log_call_with_mismatched_record_sale(self):
        """When the sale order's partner differs from the call's partner, the
        domain check fails and the wizard falls back to the call's contact."""
        call_partner = self.env["res.partner"].sudo().create({"name": "Call Partner"})
        other_partner = self.env["res.partner"].sudo().create({"name": "Other Partner"})
        other_sale_order = self.env["sale.order"].create({
            "name": "Sale Order Other",
            "partner_id": other_partner.id,
        })
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": call_partner.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="sale.order", active_id=other_sale_order.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, call_partner)
            self.assertEqual(form.res_ids, f"[{call_partner.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_action_log_call_with_matching_model_sale(self):
        """When active_model=sale.order matches a registered option (sale.order),
        the wizard should pre-select that record type and record."""
        partner = self.env["res.partner"].sudo().create({"name": "Test Partner"})
        sale_order = self.env["sale.order"].create({
            "name": "Test Sale Order",
            "partner_id": partner.id,
        })
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": partner.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="sale.order", active_id=sale_order.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "sale.order")
            self.assertEqual(form.sale_order_id, sale_order)
            self.assertEqual(form.res_ids, f"[{sale_order.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "sale.order")

    def test_log_call_domain_covers_commercial_entity_sale(self):
        """The sale order domain of the log activity wizard must cover orders
        related to every partner of the call contact's commercial entity
        (``partner`` and ``child_partner`` are siblings in TestVoipSaleCommon)."""
        own_order = self.env["sale.order"].sudo().create({"partner_id": self.partner.id})
        sibling_order = self.env["sale.order"].sudo().create({"partner_id": self.child_partner.id})
        other_partner = self.env["res.partner"].sudo().create({"name": "Unrelated Partner"})
        other_order = self.env["sale.order"].sudo().create({"partner_id": other_partner.id})
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=self.partner.id,
        ).new()
        orders = self.env["sale.order"].search(literal_eval(wizard.sale_order_id_domain))
        self.assertIn(own_order, orders, "own orders stay selectable")
        self.assertIn(
            sibling_order, orders,
            "orders of sibling contacts of the same company become selectable",
        )
        self.assertNotIn(
            other_order, orders,
            "orders of partners outside the commercial entity stay hidden",
        )
