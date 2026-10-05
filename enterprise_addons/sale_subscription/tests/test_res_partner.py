from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestResPartner(TestSubscriptionCommon):
    def test_subscription_smart_button(self):
        """A contact's subscriptions smart button should only include their orders
        or their children's orders.
        """
        test_company = self.subscription.company_id
        self.env.ref('base.user_admin').write({
            'company_ids': [(4, test_company.id)],
            'company_id': test_company.id,
        })

        tom, joe, frank = self.env['res.partner'].create([
            {'name': 'Tom'},
            {'name': 'Joe'},
            {'name': 'Frank', 'email': 'tomahawkfrank@test.com'},
        ])
        frank.parent_id = joe

        tom_sub_1 = self.subscription.copy({'partner_id': tom.id})
        tom_sub_1.action_confirm()
        tom_sub_2 = self.subscription.copy({'partner_id': tom.id})
        tom_sub_2.action_confirm()
        joe_sub = self.subscription.copy({'partner_id': joe.id})
        joe_sub.action_confirm()

        action = tom.open_related_subscription()
        self.assertEqual(self.env[action['res_model']].search(action['domain']), tom_sub_1 + tom_sub_2)
