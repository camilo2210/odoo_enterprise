from ast import literal_eval

from odoo import Command
from odoo.tests import Form, users

from .common import TestVoipSubscriptionCommon


class TestVoipCall(TestVoipSubscriptionCommon):

    def test_action_open_subscription_uses_commercial_partner(self):
        """Smart button should show subscriptions from the whole partner family (commercial partner).
        New records should default to the call's partner, not the commercial partner."""
        call = self.env["voip.call"].create({
            "partner_id": self.partner.id,
            "phone_number": "+1234567891",
            "user_id": self.user_sales_salesman.id,
        })
        self.assertEqual(call.commercial_partner_subscription_count, self.parent_partner.subscription_count)
        action = call.action_open_subscription()
        subscriptions = self.env["sale.order"].search(action["domain"])
        self.assertEqual(len(subscriptions), call.commercial_partner_subscription_count)
        self.assertEqual(action["context"]["default_partner_id"], self.partner.id)
        self.assertEqual(action["context"]["search_default_partner_id"], [self.partner.id, self.parent_partner.id])

    @users("user_sales_salesman")
    def test_action_log_call_with_mismatched_record_subscription(self):
        """When the subscription's partner differs from the call's partner,
        the domain check fails and the wizard falls back to the call's contact."""
        other_partner = self.env["res.partner"].sudo().create({"name": "Other Partner"})
        other_subscription = self.env["sale.order"].create({
            "name": "Subscription Other",
            "is_subscription": True,
            "state": "sale",
            "subscription_state": "3_progress",
            "plan_id": self.plan_month.id,
            "partner_id": other_partner.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "tax_ids": [Command.clear()],
            })],
        })
        call = self.call_1.with_env(self.env)
        with Form.from_action(
            self.env, call.action_log_call(active_model="sale.order", active_id=other_subscription.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, self.partner)
            self.assertEqual(form.res_ids, f"[{self.partner.id}]")
            self.assertEqual(form.call_id, self.call_1)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    @users("user_sales_salesman")
    def test_action_log_call_with_matching_model_subscription(self):
        """When active_model=sale.order matches a registered option (sale.order),
        the wizard should pre-select that record type and record."""
        call = self.call_1.with_env(self.env)
        with Form.from_action(
            self.env, call.action_log_call(active_model="sale.order", active_id=self.subscription_1.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "sale.order")
            self.assertEqual(form.sale_order_id, self.subscription_1)
            self.assertEqual(form.res_ids, f"[{self.subscription_1.id}]")
            self.assertEqual(form.call_id, self.call_1)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "sale.order")

    @users("user_sales_salesman")
    def test_log_call_domain_covers_commercial_entity_subscription(self):
        """The subscription domain of the log activity wizard must cover
        subscriptions related to every partner of the call contact's commercial
        entity (``partner`` is a child of ``parent_partner``)."""
        sibling_partner = self.env["res.partner"].sudo().create({
            "name": "Sibling Partner",
            "parent_id": self.parent_partner.id,
        })
        sibling_subscription = self.env["sale.order"].create({
            "name": "Sibling Subscription",
            "is_subscription": True,
            "state": "sale",
            "subscription_state": "3_progress",
            "plan_id": self.plan_month.id,
            "partner_id": sibling_partner.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "tax_ids": [Command.clear()],
            })],
        })
        unrelated_partner = self.env["res.partner"].sudo().create({"name": "Unrelated Partner"})
        unrelated_subscription = self.env["sale.order"].create({
            "name": "Unrelated Subscription",
            "is_subscription": True,
            "state": "sale",
            "subscription_state": "3_progress",
            "plan_id": self.plan_month.id,
            "partner_id": unrelated_partner.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "tax_ids": [Command.clear()],
            })],
        })
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=self.partner.with_env(self.env).id,
        ).new()
        subscriptions = self.env["sale.order"].search(literal_eval(wizard.subscription_id_domain))
        self.assertIn(self.subscription_1.with_env(self.env), subscriptions, "own subscriptions stay selectable")
        self.assertIn(
            sibling_subscription, subscriptions,
            "subscriptions of sibling contacts of the same company become selectable",
        )
        self.assertNotIn(
            unrelated_subscription, subscriptions,
            "subscriptions of partners outside the commercial entity stay hidden",
        )
