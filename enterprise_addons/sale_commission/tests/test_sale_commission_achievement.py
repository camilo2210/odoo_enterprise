# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import freeze_time, tagged
from odoo.addons.sale_commission.tests.test_sale_commission_common import TestSaleCommissionCommon


@tagged('post_install', '-at_install')
class TestSaleSubCommissionUser(TestSaleCommissionCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time("2024-04-02")
    def test_sub_commission_achievement_manager(self):
        self.commission_plan_manager.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'team',
        })
        self.commission_plan_manager.date_from = '2024-01-01'
        self.commission_plan_manager.date_to = '2024-12-31'
        (self.commission_user_1 + self.commission_user_2 + self.commission_manager).sale_team_id = self.team_commission
        self.commission_plan_manager.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 1,
            'plan_id': self.commission_plan_user.id,
        }])
        self.commission_plan_manager.user_ids = [Command.create({
            'user_id': self.commission_user_1.id,
            'date_from': "2024-01-01"
        })]
        achievement = self.env['sale.commission.achievement'].create([{
            'date': '2024-03-03',
            'achieved': 100,
            'add_user_id': self.commission_manager.id,  # Manager
            'add_plan_id': self.commission_plan_manager.id,
            'reduce_user_id': self.commission_user_1.id,  # Sale
            'reduce_plan_id': self.commission_plan_manager.id,  # same plan
        }])
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 10,
                'price_unit': 200,
            })],
            'team_id': self.commission_user_1.sale_team_id.id,
        })
        so.action_confirm()
        am = so._create_invoices()
        am._post()
        achievement.order_id = so.id
        achievement.move_id = am.id
        self.commission_plan_manager.action_approve()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        manager_achievement = achievements.filtered(lambda a: a.user_id == self.commission_manager)
        user_achievement = achievements.filtered(lambda a: a.user_id == self.commission_user_1)
        self.assertEqual(len(user_achievement), 2)
        self.assertEqual(len(manager_achievement), 2)
        self.assertAlmostEqual(sum(user_achievement.mapped('achieved')), 1900.0, msg="The user gets the amount (2000 - 100)")
        self.assertAlmostEqual(sum(manager_achievement.mapped('achieved')), 2100, msg="The manager send the amount (2000 + 100)")
        user_commissions = commissions.filtered(lambda c: c.user_id == self.commission_user_1)
        manager_commissions = commissions.filtered(lambda c: c.user_id == self.commission_manager)
        self.assertAlmostEqual(sum(user_commissions.mapped('achieved')), 1900, msg="The user gets the amount (2000 - 100)")
        self.assertAlmostEqual(sum(manager_commissions.mapped('achieved')), 2100, msg="The user gets the amount (2000 - 100)")

    @freeze_time("2024-04-01")
    def test_achievement_report_partner_id(self):
        """Ensure achievement lines carry the correct partner_id from sale order and invoice."""
        self.commission_plan_user.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
        })
        self.commission_plan_user.action_approve()

        self.commission_plan_user.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 0.1,
            'plan_id': self.commission_plan_user.id,
        }])

        self.commission_user_1.sale_team_id = self.team_commission

        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 5,
                'price_unit': 100,
            })],
            'team_id': self.commission_user_1.sale_team_id.id,
        })
        so.action_confirm()

        invoice = so._create_invoices()
        invoice._post()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([
            ('plan_id', '=', self.commission_plan_user.id),
            ('related_res_model', '=', 'account.move'),
            ('related_res_id', '=', invoice.id),
        ])
        self.assertTrue(achievements, "There should be at least one achievement line from invoice.")
        self.assertEqual(
            achievements.partner_id, invoice.partner_id,
            f"Expected partner {invoice.partner_id.name} but got {achievements.partner_id.name} on achievement line"
        )

    @freeze_time("2024-04-01")
    def test_open_achievement_with_id_above_js_safe_integer(self):
        self.commission_plan_manager.achievement_ids = [Command.create({
            'type': 'amount_invoiced',
            'rate': 1,
        })]
        self.commission_plan_manager.action_approve()

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2024-04-01',
            'invoice_user_id': self.commission_user_1.id,
            'team_id': self.team_commission.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.commission_product_1.id,
                'quantity': 1,
                'price_unit': 100,
                'tax_ids': [Command.clear()],
            })],
        })
        invoice.action_post()
        invoice_line = invoice.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        invoice_line.flush_recordset()
        self.env.cr.execute(
            "UPDATE account_move_line SET id = %s WHERE id = %s",
            (800_000_000, invoice_line.id),
        )

        achievement_report = self.env['sale.commission.achievement.report']
        achievement_report._pre_achievement_operation()
        achievement = achievement_report.search([
            ('plan_id', '=', self.commission_plan_manager.id),
            ('related_res_model', '=', 'account.move'),
            ('related_res_id', '=', invoice.id),
        ])
        achievement.ensure_one()
        self.assertGreater(achievement.id, 2**53 - 1)

        client_id = achievement.web_read({'id_str': {}})[0]['id']
        if isinstance(client_id, int):
            client_id = int(float(client_id))  # Simulate JavaScript's unsafe integer conversion.
        action = achievement_report.browse([client_id]).open_related()
        self.assertEqual(action['res_model'], invoice._name)
        self.assertEqual(action['res_id'], invoice.id)

    @freeze_time("2024-06-15")
    def test_future_dated_adjustment_visible_in_report(self):
        """Future-dated adjustments must appear in the achievement report."""
        self.commission_plan_user.write({
            'type': 'achieve',
            'user_type': 'person',
        })
        self.commission_plan_user.action_approve()

        # Create adjustment dated Dec 15
        future_adjustment = self.env['sale.commission.achievement'].create({
            'add_plan_id': self.commission_plan_user.id,
            'add_user_id': self.commission_user_1.id,
            'achieved': 1000.0,
            'date': '2024-12-15',
        })

        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([
            ('plan_id', '=', self.commission_plan_user.id),
            ('user_id', '=', self.commission_user_1.id),
            ('related_res_model', '=', 'sale.commission.achievement'),
        ])
        self.assertIn(
            future_adjustment.id, achievements.mapped('related_res_id'),
            "Adjustment dated Dec 15 must be visible when today is Jun 15"
        )
