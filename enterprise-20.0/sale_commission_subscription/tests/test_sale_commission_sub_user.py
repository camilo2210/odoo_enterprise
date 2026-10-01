# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from odoo import Command
from odoo.tests import freeze_time, tagged
from odoo.exceptions import UserError

from odoo.addons.sale_commission_subscription.tests.common import TestSaleSubscriptionCommissionCommon


@tagged('post_install', '-at_install')
class TestSaleSubCommissionUser(TestSaleSubscriptionCommissionCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def default_env_context(cls):
        # needed for mail.tracking.value test
        return {}

    def setUp(self):
        super().setUp()
        self.flush_tracking()

    def flush_tracking(self):
        """ Force the creation of tracking values. """
        self.env.flush_all()
        self.cr.flush()

    def test_sub_commission_user_achievement(self):
        with freeze_time('2024-02-02'):
            sub = self.subscription.copy()
            sub.user_id = self.commission_user_1.id
            sub.order_line.price_unit = 500
            sub.start_date = False
            sub.next_invoice_date = False
            self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'amount_invoiced',
                'rate': 0.1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }])
            sub.action_confirm()
            with self.assertRaises(UserError):
                # achievements based on sold metrics can't be used with recurring plan achievements
                self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'amount_sold',
                'rate': 0.1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }])
            self.commission_plan_sub.action_approve()
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 1000, 2, msg="The untaxed invoiced amount should be equal to 1000")
            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])

            self.assertEqual(len(commissions), 24)
            self.assertEqual(len(achievements), 1, 'The one line should count as an achievement')
            self.assertAlmostEqual(sum(achievements.mapped('achieved')), 100, 2, msg="1000 * 0.1")
            self.assertEqual(achievements.related_res_id, inv.id)
            self.assertEqual(len(commissions), 24)
            self.assertEqual(sum(commissions.mapped('commission')), 100)

        with freeze_time('2024-02-16'):
            action = sub.prepare_upsell_order()
            upsell_so = self.env['sale.order'].browse(action['res_id'])
            upsell_so.order_line.filtered(lambda l: not l.display_type).product_uom_qty = 1
            upsell_so.action_confirm()
            inv2 = upsell_so._create_invoices()
            inv2._post()
            self.assertAlmostEqual(inv2.amount_untaxed, 517.2, 2, msg="The untaxed upsell invoiced amount should be equal to 517.2")
            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])

            self.assertEqual(len(commissions), 24)
            self.assertEqual(len(achievements), 2, 'Two line should count as an achievement')
            self.assertAlmostEqual(sum(achievements.mapped('achieved')), 151.72, 2, msg="previous invoice + upsell pro-rata")
            self.assertEqual(sorted(achievements.mapped('related_res_id')), sorted([inv.id, inv2.id]))
            self.assertEqual(len(commissions), 24)
            self.assertAlmostEqual(sum(commissions.mapped('commission')), 151.72, 2)

        with freeze_time('2024-03-02'):
            inv3 = sub._create_recurring_invoice()
            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            achievements = achievements.filtered(lambda x: x.related_res_id == inv3.id and x.related_res_model == 'account.move')
            commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            self.assertEqual(len(achievements), 1, 'The one line should count as an achievement')
            commission_period = commissions.filtered(lambda x: x.target_id == achievements.target_id)

            self.assertEqual(len(commission_period), 2, "2 commissions for two users")
            self.assertEqual(sum(achievements.mapped('achieved')), 200, 'Regular invoice (doubled quantity)')
            self.assertEqual(achievements.related_res_id, inv3.id)
            self.assertEqual(sum(commission_period.mapped('commission')), 200, "One user has achieved and not the other one")

    @freeze_time('2024-02-02')
    def test_multiple_plans_conditions(self):
        sub = self.subscription.copy()
        sub.user_id = self.commission_user_1.id
        sub.order_line.price_unit = 500
        sub.start_date = False
        sub.next_invoice_date = False
        sub.action_confirm()
        self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 0.1,
            'plan_id': self.commission_plan_sub.id,
            'recurring_plan_id': sub.plan_id.id,
        }])
        self.commission_plan_user.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'amount_invoiced',
            'rate': 0.1,
            'plan_id': self.commission_plan_user.id,
        }])
        # Make sure the commissions are 100% on target, achievements force the commission rate
        self.commission_plan_user.target_commission_ids.target_rate = 1
        self.commission_plan_user.action_approve()
        self.commission_plan_sub.action_approve()
        inv_sub = sub._create_recurring_invoice()
        self.assertAlmostEqual(inv_sub.amount_untaxed, 1000, 2, msg="The amount of the recurring invoice is 1000")
        other_sale = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'order_line': [Command.create({
                'product_id': self.commission_product_1.id,
                'product_uom_qty': 1,
                'price_unit': 100,
            })],
        })
        other_sale.action_confirm()
        inv2 = other_sale._create_invoices()
        inv2._post()
        self.assertAlmostEqual(inv2.amount_untaxed, 100, 2, msg="The amount of the non recurring invoice is 100")
        self.env.invalidate_all()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])

        self.assertEqual(len(commissions), 24, "24 commissions for two users")
        self.assertEqual(sum(achievements.mapped('achieved')), 100, 'Regular invoice, 10 percent of 1000')
        self.assertEqual(achievements.related_res_id, inv_sub.id)
        self.assertEqual(sum(commissions.mapped('commission')), 100, "One user has achieved and not the other one")


        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_user.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_user.id)])
        # this plan will take both invoices: subscription and the other one because no recurring plan is defined
        self.assertEqual(len(commissions), 24, "24 commissions for two users")
        self.assertAlmostEqual(inv2.amount_untaxed, 100, 2, msg="The amount of the non recurring invoice is 100")
        self.assertEqual(sum(achievements.mapped('achieved')), 110, 'Subscription invoice provide 100 and non recurring one provives 10')
        self.assertEqual(sorted(achievements.mapped('related_res_id')), sorted([inv2.id, inv_sub.id]))
        self.assertEqual(sum(commissions.mapped('commission')), 110, "One user has achieved and not the other one")


    @freeze_time('2024-02-02')
    def test_multiple_achievements(self):
        # this test makes sure all achievements are summed even if one product is in several achievements for example
        category = self.env['product.category'].create({
            'name': 'Test Category',
        })
        self.commission_plan_sub.search([]).action_draft()
        sub = self.subscription.copy()
        sub.user_id = self.commission_user_1.id
        sub.order_line[1].unlink()
        product = sub.order_line.product_id
        product.categ_id = category.id
        sub.order_line.price_unit = 500
        sub.start_date = False
        sub.next_invoice_date = False
        self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([
            {
                'type': 'amount_invoiced',
                'rate': 0.1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }, {
                'type': 'amount_invoiced',
                'rate': 0.2,
                'plan_id': self.commission_plan_sub.id,
                'product_id': product.id,
            }, {
                'type': 'amount_invoiced',
                'rate': 0.3,
                'plan_id': self.commission_plan_sub.id,
                'product_categ_id': category.id,
            }

        ])
        self.commission_plan_user.achievement_ids = self.env['sale.commission.plan.achievement'].create([
            {
                'type': 'amount_invoiced',
                'rate': 0.1,
                'plan_id': self.commission_plan_user.id,
                'product_id': product.id,
            }, {
                'type': 'amount_invoiced',
                'rate': 0.2,
                'plan_id': self.commission_plan_user.id,
                'product_categ_id': category.id,
            }
        ])
        # Make sure the commissions are 100% on target, achievements force the commission rate
        self.commission_plan_user.target_commission_ids.target_rate = 1
        self.commission_plan_user.action_approve()
        self.commission_plan_sub.action_approve()
        sub.action_confirm()
        inv = sub._create_recurring_invoice()
        self.env.flush_all()
        self.env.invalidate_all()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
        self.assertAlmostEqual(inv.amount_untaxed, 500, 2, msg="The invoice amount should be equal to 500")
        # this plan will take both invoices: subscription and the other one because no recurring plan is defined
        self.assertEqual(len(commissions), 24, "24 commissions for two users")
        self.assertEqual(sum(achievements.mapped('achieved')), 300, 'Subscription invoice provide 300: 500*0.1 + 500*0.2+500*0.3')
        self.assertEqual(achievements.related_res_id, inv.id)
        self.assertEqual(sum(commissions.mapped('commission')), 300, "One user has achieved and not the other one")

        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_user.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_user.id)])
        self.assertAlmostEqual(inv.amount_untaxed, 500, 2, msg="The invoice amount should be equal to 500")
        # this plan will take both invoices: subscription and the other one because no recurring plan is defined
        self.assertEqual(len(commissions), 24, "24 commissions for two users")
        self.assertEqual(sum(achievements.mapped('achieved')), 150, 'invoice provide 150: 500*0.1 + 500*0.2')
        self.assertEqual(achievements.related_res_id, inv.id)
        self.assertEqual(sum(commissions.mapped('commission')), 150, "One user has achieved and not the other one")

    def test_effective_date(self):
        with freeze_time("2024-02-02"):
            sub = self.env['sale.order'].create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'user_id': self.commission_user_1.id
            })
            sub._onchange_sale_order_template_id()
            sub.order_line.price_unit = 50
            sub.start_date = False
            sub.next_invoice_date = False
            self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'mrr',
                'rate': 0.1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }])
            self.flush_tracking()
            sub.action_confirm()
            self.flush_tracking()
            self.commission_plan_sub.action_approve()
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 100, 2, msg="The untaxed invoiced amount should be equal to 1000")
            self.assertEqual(sub.recurring_monthly, 100)
            self.flush_tracking()
        with freeze_time("2024-02-03"):
            sub.order_line.product_uom_qty = 5
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 500)
            order_log_ids = sub.order_log_ids.sorted('event_date')
            sub_data = [(log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly, log.effective_date) for log in order_log_ids]
            self.assertEqual(sub_data, [
                ('0_creation', datetime.date(2024, 2, 2), '1_draft', 100, 100, datetime.date(2024, 2, 2)),
                ('1_expansion', datetime.date(2024, 2, 3), '3_progress', 400.0, 500.0, False)
            ])
            self.env.flush_all()
            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            self.assertEqual(sum(achievements.mapped('achieved')), 10, 'Regular invoice, 10 percent of 100')
            self.assertEqual(len(achievements), 1, "Only one achievement because the other log is not effective")
            self.assertEqual(achievements.related_res_model, 'sale.order')
            self.assertEqual(achievements.related_res_id, sub.id)

    def test_sub_commission_currency(self):
        """ Test that MRR log are converted in the currency of the current company.
        We need to use the currency of the log and not the company currency
        """
        self.original_get_subscription_currency_rates = self.env['sale.commission.achievement.report']._get_subscription_currency_rates
        currency_inr = self.env.ref('base.INR')
        currency_inr.active = True
        # créer pricelist INR
        # créer SO INR alors que company en USD
        # créer plan etc
        # vérifier les achievements
        inr_pricelist = self.env['product.pricelist'].create({
            'name': 'Rupee',
            'currency_id': currency_inr.id
        })
        (self.product | self.product2).subscription_rule_ids = False
        self.product.lst_price = 50
        self.product2.lst_price = 100
        with freeze_time("2024-02-02"):
            self.env['res.currency.rate'].create([{
                'rate': 60,
                'currency_id': currency_inr.id,
                'name': '2024-02-01',
            },{
                'rate': 57,
                'name': '2023-01-06',
                'currency_id': currency_inr.id,
            }, {
                'rate': 55,
                'name': '2022-01-06',
                'currency_id': currency_inr.id,
            }])
            self.env['res.currency.rate'].flush_model()
            self.env['res.currency'].flush_model()
            sub = self.env['sale.order'].create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'user_id': self.commission_user_1.id,
                'pricelist_id': inr_pricelist.id,
            })
            sub._onchange_sale_order_template_id()
            self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'mrr',
                'rate': 1, # to ease computation of currency rates, 100%
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }])
            self.flush_tracking()
            self.commission_plan_sub.action_approve()
            sub.action_confirm()
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 9000, "150 USD * 60 (currency rate)")
            self.assertEqual(sub.currency_id, inr_pricelist.currency_id)
            inv = sub._create_recurring_invoice()
            self.assertEqual(inv.currency_id, inr_pricelist.currency_id)
            self.assertAlmostEqual(inv.amount_untaxed, 9000, 2, msg="The untaxed invoiced amount should be equal to 9000")
            self.assertEqual(sub.order_log_ids.effective_date, datetime.date(2024, 2, 2))
            self.flush_tracking()
            self.env.flush_all()
            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            self.assertEqual(len(commissions), 24, "24 commissions for two users")
            self.assertAlmostEqual(sum(achievements.mapped('achieved')), 150, 0, msg='Regular invoice, 100 percent of 9000 conveted to USD = 150')
            self.assertAlmostEqual(sum(commissions.mapped('achieved')), 150, 0, msg='Regular invoice, 100 percent of 9000 conveted to USD = 150')
            self.assertAlmostEqual(sum(commissions.mapped('commission')), 150, 0, msg='Regular invoice, 100 percent of 9000 conveted to USD = 150')

    @freeze_time('2024-02-02')
    def test_commission_sub_between_different_company(self):
        other_company = self._create_company(name="Other company")
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
        company_data = self.collect_company_accounting_data(other_company)
        other_company.country_id = self.env.ref('base.fr')
        # This test only works when currency rate are synced with update_currency_rates
        # They need the currency rate 1.0 fo the currency of the existing companies
        self.env['res.currency.rate'].with_company(other_company).create({
            'currency_id': other_company.currency_id.id,
            'rate': 1.0,
            'company_id': other_company.id,
            'name': '2024-02-02'
        })
        self.env['res.currency.rate'].create({
            'currency_id': self.env.company.currency_id.id,
            'rate': 1.0,
            'company_id': self.env.company.id,
            'name': '2024-02-02'
        })
        # set the OTC in the current currency
        self.commission_plan_user.commission_amount = 90
        self.commission_plan_user.target_ids.amount = 90
        self.commission_plan_user.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'mrr',
            'rate': 0.30,
            'plan_id': self.commission_plan_user.id,
        }])
        self.commission_plan_user.target_commission_ids = [Command.create({
            'plan_id': self.commission_plan_user.id,
            'target_rate': 0,
            'amount': 0,
        }), Command.create({
            'plan_id': self.commission_plan_user.id,
            'target_rate': 1,
            'amount': self.commission_plan_user.commission_amount,
            'amount_rate': 1,
        })]
        self.commission_plan_user.action_approve()
        journal = company_data['default_journal_sale']
        self.partner.company_id = other_company.id
        self.product.product_tmpl_id.recurring_invoice = True
        self.product.with_company(other_company).subscription_rule_ids = [
            Command.clear(),
            Command.create({
                'fixed_price': 2000,
                'plan_id': self.plan_month.id,
            })]

        sub = self.env['sale.order'].with_company(other_company).create({
            'partner_id': self.partner.id,
            'user_id': self.commission_user_1.id,
            'plan_id': self.plan_month.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 10,
            })],
            'pricelist_id': new_currency_pricelist.id,
        })
        self.assertEqual(sub.currency_id, new_currency_pricelist.currency_id)
        self.assertEqual(sub.order_line.price_unit, 3000)
        self.assertEqual(sub.recurring_monthly, 30000)
        self.flush_tracking()
        sub.action_confirm()
        invoice = sub._create_invoices()
        self.flush_tracking()
        invoice.journal_id = journal.id
        invoice._post()
        self.flush_tracking()
        self.assertEqual(invoice.currency_id, inr_currency)
        self.assertEqual(invoice.amount_untaxed, 30000.0)
        self.assertEqual(sub.order_log_ids.effective_date, datetime.date(2024, 2, 2))
        self.flush_tracking()
        self.env.flush_all()
        self.env.invalidate_all()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        self.assertEqual(invoice.currency_id, inr_currency)
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_user.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_user.id)])
        self.assertEqual(achievements.currency_id, self.env.company.currency_id)
        self.assertAlmostEqual(sum(achievements.mapped('achieved')), 150, 2, msg="30000*0.3 /60")
        # 90 = is the maximum commission (100%).  30000 * 0.3 / 60 = 150 --> capped as 90
        self.assertAlmostEqual(sum(commissions.mapped('commission')), 90, 2, msg="150 achieved becomes 90")
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].with_company(other_company).search([('plan_id', '=', self.commission_plan_user.id)])
        commissions = self.env['sale.commission.report'].with_company(other_company).search([('plan_id', '=', self.commission_plan_user.id)])

        self.assertEqual(achievements.currency_id, inr_currency)
        self.assertAlmostEqual(sum(achievements.mapped('achieved')), 9000, 2, msg="30000 * 0.3 = 9000")
        # 5400 = is the maximum commission (100%) (90 x 60).  20000 * 0.3 = 6000 --> capped as 5400
        self.assertAlmostEqual(sum(commissions.mapped('commission')), 5400, 2, msg="Achieved 9003 --> commission 5400, equivalent to 90")

    def test_sub_commission_duplicated_id(self):
        # make sure two log created the same day are counted as two achievements
        first_now = datetime.datetime(2024, 2, 2, 8, 0, 0)
        second_now = datetime.datetime(2024, 3, 2, 8, 0, 0)
        third_now = datetime.datetime(2024, 3, 3, 9, 0, 0)
        with self.mock_datetime_and_now(first_now):
            sub = self.env['sale.order'].create({
                'name': 'TestSubscription Duplicated ID',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'user_id': self.commission_user_1.id
            })
            sub._onchange_sale_order_template_id()
            sub.order_line.price_unit = 50
            sub.start_date = False
            sub.next_invoice_date = False
            self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'mrr',
                'rate': 0.1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }])
            self.flush_tracking()
            sub.action_confirm()
            self.flush_tracking()
            self.commission_plan_sub.action_approve()
            inv = sub._create_recurring_invoice()
            self.assertAlmostEqual(inv.amount_untaxed, 100, 2, msg="The untaxed invoiced amount should be equal to 1000")
            self.assertEqual(sub.recurring_monthly, 100)
            self.flush_tracking()
        with self.mock_datetime_and_now(second_now):
            sub.order_line.product_uom_qty = 5
            self.flush_tracking()
        with self.mock_datetime_and_now(third_now):
            sub.order_line.product_uom_qty = 10
            self.flush_tracking()
            self.assertEqual(sub.recurring_monthly, 1000, "We need to logs on the same date")
            inv = sub._create_invoices()
            inv._post()
            self.flush_tracking()  # needed to run precommit _update_effective_date

            self.env.invalidate_all()
            order_log_ids = sub.order_log_ids.sorted('id')
            sub_data = [(
                log.event_type,
                log.event_date,
                log.subscription_state,
                log.amount_signed,
                log.recurring_monthly,
                log.effective_date,
                log.create_date
            ) for log in order_log_ids]
            self.assertEqual(sub_data, [
                ('0_creation', datetime.date(2024, 2, 2), '1_draft', 100.0, 100.0, datetime.date(2024, 2, 2), datetime.datetime(2024, 2, 2, 8, 0)),
                ('1_expansion', datetime.date(2024, 3, 2), '3_progress', 400.0, 500.0, datetime.date(2024, 3, 2), datetime.datetime(2024, 3, 2, 8, 0)),
                ('1_expansion', datetime.date(2024, 3, 3), '3_progress', 500.0, 1000.0, datetime.date(2024, 3, 2), datetime.datetime(2024, 3, 3, 9, 0))
            ])

            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            self.assertEqual(sum(achievements.mapped('achieved')), 100, 'Regular invoice, 10 percent of 100')
            self.assertEqual(len(achievements), 3, "3 achievements")
            self.assertEqual(achievements.mapped('related_res_id'), [sub.id, sub.id, sub.id])
            # remove duplicates
            achievement_ids = set(achievements.ids)
            self.assertEqual(len(achievement_ids), 3, "Three achievements should have different ids")

    def test_sub_commission_transfer(self):
        # Ensure transfer logs are taken into account
        with freeze_time('2024-06-01'):
            #  monthly
            sub = self.subscription.copy()
            sub.user_id = self.commission_user_1.id

            self.sub_product_tmpl.subscription_rule_ids.filtered(lambda s: s.plan_id == self.plan_month).fixed_price = 100
            self.sub_product_tmpl.subscription_rule_ids.filtered(lambda s: s.plan_id == self.plan_year).fixed_price = 1000
            sub.order_line = [Command.clear()]
            sub.order_line = [
            (0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
            })]
            sub.start_date = False
            sub.next_invoice_date = False
            self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'mrr',
                'rate': 0.8,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': self.plan_month.id,
            }, {
                'type': 'mrr',
                'rate': 1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': self.plan_year.id,
            }])
            self.commission_plan_sub.action_approve()
            self.flush_tracking()
            sub.prepayment_percent = 0
            sub.action_confirm()
            self.flush_tracking()
            sub._create_recurring_invoice()

        with freeze_time('2024-07-01'):
            self.flush_tracking()
            action = sub.prepare_renewal_order()
            renewal_so = self.env['sale.order'].browse(action['res_id'])
            renewal_so.plan_id = self.plan_year.id
            self.flush_tracking()
            renewal_so.action_confirm()
            self.flush_tracking()
            renewal_so._create_recurring_invoice()
            self.flush_tracking()
            order_log_ids = sub.order_log_ids.sorted('event_date')
            sub_data = [
                (log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly, log.effective_date)
                for log in order_log_ids]

            self.assertEqual(sub_data, [('0_creation', datetime.date(2024, 6, 1), '1_draft', 100, 100, datetime.date(2024, 6, 1)),
                                        ('3_transfer', datetime.date(2024, 7, 1), '5_renewed', -100.0, 0.0, datetime.date(2024, 7, 1))])
            order_log_ids = renewal_so.order_log_ids.sorted('event_date')
            renew_data = [
                (log.event_type, log.event_date, log.subscription_state, log.amount_signed, log.recurring_monthly, log.effective_date)
                for log in order_log_ids]

            self.assertEqual(renew_data, [('3_transfer', datetime.date(2024, 7, 1), '2_renewal', 100.0, 100.0, datetime.date(2024, 7, 1)),
                                          ('15_contraction', datetime.date(2024, 7, 1), '3_progress', -16.67, 83.33, datetime.date(2024, 7, 1))])

            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            self.assertEqual(len(achievements), 4, 'We should have 4 ahcievements: creation, 2 transfer and one contraction')
            self.assertEqual(sum(achievements.mapped('achieved')), 83.33, '80 - 80 + 100 - 16.87')
            self.assertEqual(sum(commissions.mapped('commission')), 83.33, "Commission = achieved in this case")

    def test_sub_commission_no_currency_rate(self):
        """Test that commissions work correctly when res_currency_rate table is empty."""
        self.env['res.currency.rate'].sudo().search([]).unlink()

        with freeze_time("2024-02-03"):
            sub = self.env['sale.order'].create({
                'name': 'TestSubscription',
                'is_subscription': True,
                'plan_id': self.plan_month.id,
                'note': "original subscription description",
                'partner_id': self.user_portal.partner_id.id,
                'sale_order_template_id': self.subscription_tmpl.id,
                'user_id': self.commission_user_1.id
            })
            sub._onchange_sale_order_template_id()
            sub.order_line.price_unit = 50
            self.commission_plan_sub.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
                'type': 'mrr',
                'rate': 0.1,
                'plan_id': self.commission_plan_sub.id,
                'recurring_plan_id': sub.plan_id.id,
            }])
            self.flush_tracking()
            sub.action_confirm()
            self.flush_tracking()
            self.commission_plan_sub.action_approve()
            sub._create_recurring_invoice()
            self.flush_tracking()
            self.env.flush_all()
            self.env.invalidate_all()
            self.env['sale.commission.achievement.report']._pre_achievement_operation()
            achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_sub.id)])
            self.assertEqual(sum(achievements.mapped('achieved')), 10, 'Regular invoice, 10 percent of 100')
            self.assertEqual(sum(commissions.mapped('commission')), 10, 'Regular invoice, 10 percent of 100')

    @freeze_time('2024-02-02')
    def test_dynamic_mrr_plan(self):
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
            'type': 'mrr',
            'rate': 0.5,
            'plan_id': commission_other.id,
            'recurring_plan_id': self.plan_month.id,
        }])
        commission_other.target_ids.amount = 75
        commission_other.user_ids = self.env['sale.commission.plan.user'].create([{
            'user_id': self.env.user.id,
            'plan_id': commission_other.id,
        }])
        commission_other.action_approve()
        commission_not_taken = commission_other.copy()
        # ensure that we don't take into account the commissions of this plan because it is not used in the dynamic_plan_ids field
        commission_not_taken.action_approve()
        self.commission_plan_manager.write({
            'periodicity': 'month',
            'type': 'achieve',
            'user_type': 'person',
            'target_type': 'dynamic',
            'dynamic_plan_ids': [Command.link(commission_other.id)]
        })
        self.commission_plan_manager.achievement_ids = self.env['sale.commission.plan.achievement'].create([{
            'type': 'mrr',
            'rate': 0.5,
            'plan_id': self.commission_plan_user.id,
            'recurring_plan_id': self.plan_month.id,
        }])
        # The sale order log done by the create_uid of the self.commission_manager are taken into account into the commission
        self.commission_plan_manager.user_ids.user_id = self.commission_manager
        self.commission_plan_manager.user_ids.user_ids = [Command.link(self.env.user.id)]
        self.commission_plan_manager.action_approve()
        self.flush_tracking()
        sub = self.env['sale.order'].create({
            'name': 'TestSubscription',
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'note': "original subscription description",
            'partner_id': self.user_portal.partner_id.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })
        sub._onchange_sale_order_template_id()
        sub.order_line.price_unit = 100
        self.flush_tracking()
        sub.action_confirm()
        self.flush_tracking()
        am = sub._create_recurring_invoice()
        self.flush_tracking()
        self.env.flush_all()
        self.env.invalidate_all()
        self.env['sale.commission.achievement.report']._pre_achievement_operation()
        achievements = self.env['sale.commission.achievement.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        commissions = self.env['sale.commission.report'].search([('plan_id', '=', self.commission_plan_manager.id)])
        self.assertEqual(am.invoice_user_id, self.env.user)
        self.assertEqual(sub.order_log_ids.user_id, self.env.user)
        self.assertAlmostEqual(achievements.achieved, 100, msg="The achieved amount should be 100, 200/2")
        self.assertAlmostEqual(sum(commissions.mapped('commission')), 100, msg="The achieved amount should be 100")
        self.assertEqual(commissions.mapped('target_amount'), [75.0, 75.0, 75.0, 75.0, 75.0, 75.0, 75.0, 75.0, 75.0, 75.0, 75.0, 75.0])
        self.assertEqual(achievements.document_user_id, sub.user_id, "Dynamic plan can have document_user_id")
