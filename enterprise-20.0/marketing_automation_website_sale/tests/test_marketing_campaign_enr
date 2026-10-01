from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.tests.common import WebsiteSaleCommon
from odoo.tests import tagged, users


@tagged("marketing_automation", "ma_enroll", "ma_enroll_action")
class TestCampaignEnrollProduct(MarketingAutomationCommon, PaymentCommon, WebsiteSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.product_campaign = cls.env['marketing.campaign'].create({
            'enroll_action_type': 'product_cart',
            'enroll_type': 'action',
            'model_id': cls.env['ir.model']._get_id('res.partner'),
            'product_ids': [(6, 0, cls.product.ids)],
            'title': 'Product Campaign',
        })
        cls._create_activity_mail(cls.product_campaign, cls.user_marketing_automation)

        cls.WebsiteSaleCartController = Cart()

    @users('user_marketing_automation')
    def test_enroll_product_fields(self):
        """ Assert constraints and field coherency """
        campaign = self.product_campaign.with_env(self.env)
        self.assertEqual(campaign.product_ids, self.product)

        # should reset
        campaign.write({'enroll_type': 'on_demand'})
        campaign.flush_recordset()
        self.assertFalse(campaign.product_ids)

    @users("user_marketing_automation")
    def test_enroll_action_product_bought(self):
        product_campaign = self.product_campaign.with_env(self.env)
        product_campaign.write({
            'enroll_action_type': 'product_bought',
        })
        self._launch_campaign(product_campaign)
        self.assertFalse(product_campaign.participant_ids)

        with self.mock_request(user=self.env.user) as request:
            self.WebsiteSaleCartController.add_to_cart(
                product_template_id=self.product.product_tmpl_id,
                product_id=self.product.id,
                quantity=1
            )
            # product added to cart => no participant
            self.assertEqual(len(product_campaign.participant_ids), 0)
            request.cart._validate_order()
            # product bought => add participant
            self.assertEqual(len(product_campaign.participant_ids), 1)

    @users("user_marketing_automation")
    def test_enroll_action_product_cart(self):
        product_campaign = self.product_campaign.with_env(self.env)
        product_campaign.write({
            'enroll_action_type': 'product_cart',
        })
        self._launch_campaign(product_campaign)
        self.assertFalse(product_campaign.participant_ids)

        with self.mock_request(user=self.env.user):
            # Update cart value to trigger the participant creation
            self.WebsiteSaleCartController.add_to_cart(
                product_template_id=self.product.product_tmpl_id,
                product_id=self.product.id,
                quantity=1
            )
            self.assertEqual(len(self.product_campaign.with_env(self.env).participant_ids), 1)
