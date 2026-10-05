# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.pos_sale_commission.tests.test_pos_sale_commission_common import TestPOSSaleCommissionCommon
from odoo.tests import freeze_time


class TestSaleCommissionDynamic(TestPOSSaleCommissionCommon):

    @freeze_time('2024-02-02')
    def test_pos_commission_team(self):
        self.commission_product_1.lst_price = 100
        self.commission_plan_manager.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'team',
        })
        (self.commission_user_1 + self.commission_user_2 + self.commission_manager).sale_team_id = self.team_commission

        self.commission_plan_manager.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_sold_pos',
            'rate': 0.1,
            'plan_id': self.commission_plan_user.id,
        }, {
            'type': 'qty_sold_pos',
            'rate': 0.5,
            'product_id': self.commission_product_1.id,
            'plan_id': self.commission_plan_user.id,
        }])

        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_1.id,
                'pricelist_id': self.partner_1.property_product_pricelist.id,
                'user_id': self.commission_user_1.id,
                'crm_team_id': self.team_commission.id,
            },
            'line_data': [
                {'product_id': self.commission_product_1.id},
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id, 'amount': 10},
                {'payment_method_id': self.bank_payment_method.id},
            ],
            'pos_config': self.pos_config_eur,
        })
        self.assertEqual(order.state, 'paid')
        self.assertAlmostEqual(order.amount_total, 115, 2, msg="The amount is 115 (15% tax)")

        self.commission_plan_manager.action_approve()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        self.assertEqual(len(achievements), 1, 'The one line should count as an achievement')
        self.assertEqual(achievements.user_id.id, self.commission_manager.id)
        self.assertEqual(sum(achievements.mapped('achieved')), 10.5, "10% of 100 and 50% of 1")
        self.assertEqual(achievements.related_res_id, order.id)
        self.assertEqual(sum(commissions.mapped('commission')), 10.5, 'same as achievement')
        self.assertEqual(achievements.user_id.id, self.commission_manager.id)

    @freeze_time('2024-02-02')
    def test_pos_commission_user(self):
        self.commission_product_1.lst_price = 100
        self.commission_plan_manager.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
        })
        self.commission_plan_manager.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_sold_pos',
            'rate': 0.1,
            'plan_id': self.commission_plan_user.id,
        }, {
            'type': 'qty_sold_pos',
            'rate': 0.5,
            'product_id': self.commission_product_1.id,
            'plan_id': self.commission_plan_user.id,
        }])

        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_1.id,
                'pricelist_id': self.partner_1.property_product_pricelist.id,
                'user_id': self.commission_user_1.id,
                'crm_team_id': self.team_commission.id,
            },
            'line_data': [
                {'product_id': self.commission_product_1.id},
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id, 'amount': 10},
                {'payment_method_id': self.bank_payment_method.id},
            ],
            'pos_config': self.pos_config_eur,
        })
        self.assertEqual(order.state, 'paid')
        self.assertAlmostEqual(order.amount_total, 115, 2, msg="The amount is 115 (15% tax)")

        self.commission_plan_manager.action_approve()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        self.assertFalse(achievements, "The manager don't have any achievement")
        self.commission_plan_manager.user_ids.user_id = self.commission_user_1.id

        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])

        self.assertEqual(len(achievements), 1, 'The one line should count as an achievement')
        self.assertEqual(achievements.user_id, self.commission_user_1)
        self.assertEqual(sum(achievements.mapped('achieved')), 10.5, "10% of 100 and 50% of 1")
        self.assertEqual(achievements.related_res_id, order.id)
        self.assertEqual(sum(commissions.mapped('commission')), 10.5, 'same as achievement')
