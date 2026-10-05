from odoo import Command
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


class TestVoipSubscriptionCommon(TestSubscriptionCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_sales_salesman = cls.env["res.users"].create({
            "login": "user_sales_salesman",
            "name": "user_sales_salesman",
            "email": "user_sales_salesman@example.com",
            "group_ids": [Command.link(cls.env.ref("sales_team.group_sale_salesman").id)],
        })
        cls.user_sales_manager = cls.env["res.users"].create({
            "login": "user_sales_manager",
            "name": "user_sales_manager",
            "email": "user_sales_manager@example.com",
            "group_ids": [Command.link(cls.env.ref("sales_team.group_sale_manager").id)],
        })
        cls.parent_partner = cls.env["res.partner"].create({
            "name": "we are family",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
            "phone": "110",
            "parent_id": cls.parent_partner.id,
        })
        cls.subscription_1 = cls.env['sale.order'].create({
            'name': 'Test Subscription 1',
            'is_subscription': True,
            'state': 'sale',
            'subscription_state': '3_progress',
            'plan_id': cls.plan_month.id,
            'partner_id': cls.partner.id,
            'user_id': cls.user_sales_salesman.id,
            'order_line': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'tax_ids': [Command.clear()],
            })],
        })
        cls.subscription_2 = cls.env['sale.order'].create({
            'name': 'Test Subscription 2',
            'is_subscription': True,
            'state': 'sale',
            'subscription_state': '6_churn',
            'plan_id': cls.plan_month.id,
            'partner_id': cls.partner.id,
            'user_id': cls.user_sales_manager.id,
            'order_line': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'tax_ids': [Command.clear()],
            })],
        })
        cls.call_1 = cls.env["voip.call"].create({
            "partner_id": cls.partner.id,
            "phone_number": "110",
            "user_id": cls.user_sales_salesman.id,
        })
        cls.call_2 = cls.env["voip.call"].create({
            "partner_id": cls.partner.id,
            "phone_number": "110",
            "user_id": cls.user_sales_manager.id,
        })
