# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.fields import Command
from odoo.tests import tagged, users

from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSaleSubscriptionProductTemplate(TestSubscriptionCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.subscription_product = cls._create_product(
            subscription_rule_ids=[
                Command.create({'plan_id': cls.plan_week.id, 'fixed_price': 5}),
                Command.create({'plan_id': cls.plan_month.id, 'fixed_price': 15}),
            ],
        )

    @users('salesman')
    def test_sale_subscription_get_configurator_display_price(self):
        configurator_price = self.env['product.template']._get_configurator_display_price(
            product_or_template=self.subscription_product,
            quantity=3,
            date=datetime(2000, 1, 1),
            currency=self.currency,
            pricelist=self.pricelist,
            plan_id=self.plan_month.id,
        )

        self.assertEqual(configurator_price[0], 15)

    @users('salesman')
    def test_sale_subscription_get_additional_configurator_data(self):
        configurator_data = self.env['product.template']._get_additional_configurator_data(
            product_or_template=self.subscription_product,
            date=datetime(2000, 1, 1),
            currency=self.currency,
            pricelist=self.pricelist,
            plan_id=self.plan_month.id,
        )

        self.assertEqual(configurator_data['price_info'], "per month")

    def test_subscription_import_with_recurring_invoice_changed(self):
        """
        Checks that an error is raised when trying to import a subscription that already has been sold, if in the
        import fields, the recurrence has changed.
        """
        self.subscription.action_confirm()
        self.subscription._create_invoices()
        self.env.flush_all()
        fields = ['id', 'name', 'recurring_invoice']
        export = self.subscription.order_line[0].product_id[0].export_data(fields)
        rows = export['datas']
        rows[0][2] = "False"
        result = self.env['product.product'].with_context({'import_file': True}).load(fields, rows)
        self.assertEqual(result['messages'][0]['type'], 'error')
