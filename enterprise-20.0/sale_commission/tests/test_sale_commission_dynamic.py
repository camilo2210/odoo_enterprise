import datetime
from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale_commission.tests.test_sale_commission_common import TestSaleCommissionCommon


@tagged('post_install', '-at_install')
class TestSaleCommissionDynamic(TestSaleCommissionCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2024-02-02')
    def test_commission_user_ids(self):
        """ Ensure the achievement of team member are taken into account
        We need to ensure that the achievements of user_ids on sale.commission.plan.user
        are assigned to the user_id
        """
        vals = [{
            'login': "New Sales 1",
            'partner_id': self.env['res.partner'].create({
                'name': "Sales 1",
                'email': "sales1@example.com",
            }).id,
            'group_ids': [Command.set(self.env.ref('sales_team.group_sale_salesman').ids)],
        }, {
            'login': "New Sales 2",
            'partner_id': self.env['res.partner'].create({
                'name': "Sales 2",
                'email': "sales2@example.com",
            }).id,
            'group_ids': [Command.set(self.env.ref('sales_team.group_sale_salesman').ids)],
        }, {
            'login': "New Sales 3",
            'partner_id': self.env['res.partner'].create({
                'name': "Sales 3",
                'email': "sales3@example.com",
            }).id,
            'group_ids': [Command.set(self.env.ref('sales_team.group_sale_salesman').ids)],
        }]
        users = self.env['res.users'].create(vals)
        subordonate_1 = users[0]
        subordonate_2 = users[1]
        manager2 = users[2]
        commission_other = self.env['sale.commission.plan'].create({
            'name': "Other plan",
            'company_id': self.env.company.id,
            'date_from': datetime.date(year=2024, month=1, day=1),
            'date_to': datetime.date(year=2024, month=12, day=31),
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
            'target_type': 'static',

        })
        commission_other.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 0.5,
            'plan_id': commission_other.id,
        }])
        commission_other.target_ids.amount = 100
        commission_other.user_ids = self.env['sale.commission.plan.user'].create([{
            'user_id': subordonate_1.id,
            'plan_id': commission_other.id,
        }])
        commission_other.action_approve()
        commission_other2 = commission_other.copy()
        commission_other2.name = "Other Plan 2"
        commission_other2.target_ids.amount = 300
        commission_other2.user_ids.user_id = subordonate_2.id
        commission_other2.action_approve()
        commission_not_taken = commission_other.copy()
        commission_not_taken.name = "Not used plan"
        # ensure that we don't take into account the commissions of this plan because it is not used in the dynamic_plan_ids field
        commission_not_taken.action_approve()
        self.commission_plan_manager.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
            'dynamic_plan_ids': [Command.link(commission_other.id), Command.link(commission_other2.id)]
        })
        self.commission_plan_manager.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 0.5,
            'plan_id': self.commission_plan_manager.id,
        }])
        # The invoices done by the create_uid of the self.commission_manager are taken into account into the commission
        self.commission_plan_manager.user_ids.user_id = self.commission_manager
        self.commission_plan_manager.user_ids[0].user_ids = [Command.link(subordonate_1.id)]
        self.commission_plan_manager.user_ids = [Command.create({
            'user_id': manager2.id,
            'user_ids': [Command.link(subordonate_2.id)],
        })]
        self.commission_plan_manager.action_approve()
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': subordonate_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 1,
                'price_unit': 20,
            })],
        })
        so2 = so.copy(default={'user_id': subordonate_2.id})
        so2.order_line.price_unit = 42
        so.action_confirm()
        so2.action_confirm()
        am = so._create_invoices()
        am._post()
        am2 = so2._create_invoices()
        am2._post()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        all_achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        achievements = all_achievements.filtered(lambda x: x.related_res_id == am.id and x.related_res_model == 'account.move')
        all_commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = all_commissions.filtered(lambda c: c.user_id == self.commission_manager)

        self.assertEqual(am.invoice_user_id, subordonate_1)
        self.assertEqual(am2.invoice_user_id, subordonate_2)
        self.assertAlmostEqual(achievements.achieved, 10, msg="The achieved amount should be 10")
        self.assertAlmostEqual(sum(commissions.mapped('commission')), 10, msg="The achieved amount should be 10")
        self.assertEqual(commissions.mapped('target_amount'), [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
        self.assertEqual(achievements.document_user_id, so.user_id, "Dynamic plan can have document_user_id")

        achievements = all_achievements.filtered(lambda x: x.related_res_id == am2.id and x.related_res_model == 'account.move')
        commissions = all_commissions.filtered(lambda c: c.user_id == manager2)

        self.assertAlmostEqual(achievements.achieved, 21, msg="The achieved amount should be 21")
        self.assertAlmostEqual(sum(commissions.mapped('commission')), 21, msg="The achieved amount should be 21")
        self.assertEqual(commissions.mapped('target_amount'), [300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0])
        self.assertEqual(achievements.document_user_id, so2.user_id, "Dynamic plan can have document_user_id")

    @freeze_time('2026-05-11')
    def test_commission_dynamic_gap_overlap(self):
        plan = self.env['sale.commission.plan'].create({
            'name': "Test dynamic plan",
            'company_id': self.env.company.id,
            'date_from': datetime.date(year=2026, month=1, day=1),
            'date_to': datetime.date(year=2026, month=12, day=31),
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
            'dynamic_plan_ids': [Command.link(self.commission_plan_user.id)],

        })
        plan.user_ids = [
            Command.create({
                'user_id': self.commission_manager.id,
                'user_ids': [Command.link(self.commission_user_1.id), Command.link(self.commission_user_2.id)],
            }),
            Command.create({
                'user_id': self.commission_manager.id,
                'user_ids': [Command.link(self.commission_user_1.id)],
        })]
        plan_user_1 = plan.user_ids[0]
        plan_user_2 = plan.user_ids[1]
        plan_user_1.date_to = datetime.date(2026, 4, 30)
        plan_user_2.date_from = datetime.date(2026, 5, 1)
        plan.user_ids.flush_recordset()
        wiz = self.env['sale.commission.plan.issue.wizard'].new({'plan_ids': [Command.link(plan.id)]})
        self.assertFalse(wiz.issue_user_ids, "No issue should be found")
        with self.assertRaises(UserError):
            plan_user_1.date_to = datetime.date(2026, 5, 1)
        plan_user_1.date_to = datetime.date(2026, 4, 30)
        plan_user_2.date_from = datetime.date(2026, 6, 1)
        plan.user_ids.flush_recordset()
        wiz2 = self.env['sale.commission.plan.issue.wizard'].new({'plan_ids': [Command.link(plan.id)]})
        self.assertEqual(wiz2.issue_user_ids.date_from, datetime.date(2026, 4, 30), "date_from = date_to and it causes issue")
        self.assertEqual(wiz2.issue_user_ids.date_to, datetime.date(2026, 6, 1), "date_from = date_to and it causes issue")
        self.assertEqual(wiz2.issue_user_ids.issue_type, "gap", "May is not covered")
        plan_user_2.date_from = datetime.date(2026, 4, 1)
        plan.user_ids.flush_recordset()

        wiz2 = self.env['sale.commission.plan.issue.wizard'].new({'plan_ids': [Command.link(plan.id)]})
        self.assertEqual(wiz2.issue_user_ids.date_from, datetime.date(2026, 4, 1), "Overlap in April")
        self.assertEqual(wiz2.issue_user_ids.date_to, datetime.date(2026, 4, 30), "Overlap in April")
        self.assertEqual(wiz2.issue_user_ids.issue_type, "overlap", "April is counted twice")
        with self.assertRaises(UserError):
            #  we can't update the periodicty without updating the date_from and date_to values
            plan.periodicity = 'quarter'

    @freeze_time('2024-12-02')
    def test_dynamic_currency_rate(self):
        other_company = self._create_company(name="Other company")
        company_data = self.collect_company_accounting_data(other_company)
        inr_currency = self.env.ref('base.INR')
        inr_currency.active = True
        other_company.currency_id = inr_currency.id
        new_currency_pricelist = self.env['product.pricelist'].with_company(other_company).create({'name': 'TEST', 'currency_id': inr_currency.id})
        # Conversion from current company (USD) to INR
        self.env['res.currency.rate'].create({
            'currency_id': inr_currency.id,
            'rate': 60,
            'company_id': self.env.company.id,
        })
        usd_currency = self.env.company.currency_id
        # Conversion from other company (INR) to USD
        self.env['res.currency.rate'].with_company(other_company).create({
            'currency_id': usd_currency.id,
            'rate': 1 / 60,
            'company_id': other_company.id,
        })
        other_company.country_id = self.env.ref('base.fr')
        static_plan = self.commission_other.copy(default={'company_id': other_company.id})
        static_plan.name = "Static Plan INR"
        static_plan.user_ids.user_id = self.commission_user_1
        self.assertEqual(static_plan.currency_id, inr_currency)
        static_plan.target_ids.amount = 60000
        self.dynamic_plan.dynamic_plan_ids = [Command.set(static_plan.ids)]
        self.dynamic_plan.user_ids.user_ids = self.commission_user_1
        self.dynamic_plan.user_ids.user_ids
        self.dynamic_plan.name = "Dynamic Plan (USD)"
        self.dynamic_plan.action_approve()
        static_plan.action_approve()

        journal = company_data['default_journal_sale']
        so = self.env['sale.order'].with_company(other_company).create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 10,
                'price_unit': 6000,
            })],
            'pricelist_id': new_currency_pricelist.id,
        })
        so.action_confirm()
        invoice = so._create_invoices()
        invoice.journal_id = journal.id
        invoice._post()
        self.assertEqual(invoice.currency_id, inr_currency)
        self.assertEqual(invoice.currency_id, inr_currency)
        self.assertEqual(invoice.amount_untaxed, 60000)
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', 'in', self.dynamic_plan.ids + static_plan.ids)])
        commissions = self.env['sale.commission.report'].search([('plan_id', 'in', self.dynamic_plan.ids + static_plan.ids)])
        self.assertEqual(achievements.currency_id, self.env.company.currency_id)
        #  The other plan has achievement rate of 5%
        #  The manager plan has achievement rate of 100%
        self.assertEqual(achievements.sorted('achieved').mapped('achieved'), [50, 1000], "The achievement is 1000 in USD")
        self.assertEqual(achievements.sorted('target_amount').mapped('target_amount'), [1000, 1000], "The achievement is 1000 in USD")
        all_1000 = [v == 1000 for v in commissions.mapped('target_amount')]
        self.assertTrue(all(all_1000), "All target amount are equal to 1000 (the target of the static plan)")
        self.assertEqual(commissions.sorted('commission').mapped('commission'), [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 1000.0])
        # check in another currnecy
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].with_company(other_company).search([('plan_id', 'in', self.dynamic_plan.ids + static_plan.ids)])
        commissions = self.env['sale.commission.report'].with_company(other_company).search([('plan_id', 'in', self.dynamic_plan.ids + static_plan.ids)])
        self.assertEqual(achievements.currency_id, other_company.currency_id)
        self.assertEqual(achievements.sorted('achieved').mapped('achieved'), [3000, 60000], "The achievement is 1000 in USD")
        all_1000 = [v == 60000 for v in commissions.mapped('target_amount')]
        self.assertTrue(all(all_1000), "All target amount are equal to 60000 (the target of the static plan)")
        self.assertEqual(commissions.sorted('commission').mapped('commission'), [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3000.0, 60000.0])
