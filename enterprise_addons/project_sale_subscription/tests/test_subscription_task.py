# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import datetime

from odoo import fields, Command
from odoo.tests import tagged
from odoo.exceptions import UserError
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('-at_install', 'post_install')
class TestSubscriptionTask(TestSubscriptionCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.quick_ref('project.group_project_manager')
        cls.env.user.group_ids += cls.env.ref('project.group_project_recurring_tasks')
        cls.project = cls.env['project.project'].with_context({'mail_create_nolog': True}).create({
            'name': 'Project',
            'type_ids': [
                Command.create({'name': 'a'}),
                Command.create({'name': 'b'}),
            ],
            'allow_billable': True,
        })

        cls.product_no_recurrence, cls.product_recurrence = cls.env['product.template'].create([{
            'name': 'Product No Recurrence',
            'type': 'service',
            'project_id': cls.project.id,
            'service_tracking': 'task_global_project',
        }, {
            'name': 'Product Recurrence',
            'recurring_invoice': True,
            'type': 'service',
            'project_id': cls.project.id,
            'service_tracking': 'task_global_project',
        }])

    def test_task_recurrence(self):
        Order = self.env['sale.order']
        OrderLine = self.env['sale.order.line']
        self.product_recurrence.project_id.allow_recurring_tasks = True
        for product in [
            self.product_no_recurrence,
            self.product_recurrence,
        ]:
            is_recurrent = product.recurring_invoice
            for end_date in fields.Date.today() + relativedelta(months=1), False:
                order = Order.create({
                    'is_subscription': True,
                    'note': "original subscription description",
                    'partner_id': self.partner.id,
                    **({
                        'plan_id': self.plan_month.id,
                        'end_date': end_date,
                    } if is_recurrent else {}),
                })
                order_line = OrderLine.create({
                    'order_id': order.id,
                    'product_id': product.product_variant_id.id,
                })
                order.action_confirm()
                self.assertFalse(order_line.task_id.recurring_task,
                                 "The task created should not be recurrent even if the product is recurrent")

    def test_task_plan_close(self):
        order = self.env['sale.order'].create({
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'note': "original subscription description",
            'partner_id': self.partner.id,
        })
        order_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        })
        self.product_recurrence.project_id.allow_recurring_tasks = True
        order.action_confirm()
        task = order_line.task_id
        self.assertFalse(task.recurring_task, "Task should not be recurrent")
        self.assertFalse(task.recurrence_id, "Task should not be recurrent")
        recurrence = self.env['project.task.recurrence'].create({
            'task_ids': task.ids,
            'repeat_interval': 1,
            'repeat_unit': 'week',
            'repeat_type': 'forever',
        })
        task.write({
            'recurring_task': True,
            'recurrence_id': recurrence.id,
        })
        order.set_close()
        self.assertFalse(task.recurring_task, "Closing a subscription must stop the task recurrence")
        self.assertFalse(task.recurrence_id, "Closing a subscription must stop the task recurrence")

    def test_task_plan_cancel(self):
        order = self.env['sale.order'].create({
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'note': "original subscription description",
            'partner_id': self.partner.id,
        })
        order_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        })
        self.product_recurrence.project_id.allow_recurring_tasks = True
        order.action_confirm()
        task = order_line.task_id
        self.assertFalse(task.recurring_task, "Task should not be recurrent")
        self.assertFalse(task.recurrence_id, "Task should not be recurrent")
        recurrence = self.env['project.task.recurrence'].create({
            'task_ids': task.ids,
            'repeat_interval': 1,
            'repeat_unit': 'week',
            'repeat_type': 'forever',
        })
        task.write({
            'recurring_task': True,
            'recurrence_id': recurrence.id,
        })
        order._action_cancel()
        self.assertFalse(task.recurring_task, "Cancelling a subscription must stop the task recurrence")
        self.assertFalse(task.recurrence_id, "Cancelling a subscription must stop the task recurrence")

    def test_task_generation(self):
        product_task = self.env['product.template'].create({
            'name': 'Product task',
            'type': 'service',
            'recurring_invoice': True,
            'project_id': self.project.id,
            'service_tracking': 'task_global_project',
        })
        order = self.env['sale.order'].create({
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'note': "original subscription description",
            'partner_id': self.partner.id,
        })
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product_task.product_variant_id.id,
        })

        order.action_confirm()
        self.assertEqual(len(order.tasks_ids), 1, "One task should be created")
        order._create_recurring_invoice()
        action = order.prepare_upsell_order()
        upsell = self.env['sale.order'].browse(action['res_id'])

        upsell.order_line[:1].product_uom_qty = 1
        upsell.action_confirm()
        self.assertEqual(len(order.tasks_ids), 1, "No additional task should be created")
        action = order.prepare_renewal_order()
        renew = self.env['sale.order'].browse(action['res_id'])

        renew.order_line[:1].product_uom_qty = 2
        renew.action_confirm()
        self.assertEqual(len(renew.tasks_ids), 1, "One task for renew should be created")

    def test_task_creation_on_non_recurring_product_upsell(self):
        subscription = self.env['sale.order'].create({
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'note': "original subscription description",
            'partner_id': self.partner.id,
            'sale_order_template_id': self.subscription_tmpl.id,
        })

        self.env['sale.order.line'].create([{
            'order_id': subscription.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }])

        subscription.action_confirm()
        invoice = subscription._create_invoices(final=True)
        invoice.action_post()
        task_domain = [('project_id', '=', self.project.id)]
        self.assertEqual(len(self.env['project.task'].search(task_domain)), 1, 'Task should be created')

        action = subscription.prepare_upsell_order()
        upsell = self.env['sale.order'].browse(action['res_id'])

        upsell.order_line.filtered(lambda sol: not sol.display_type).product_uom_qty = 1
        self.env['sale.order.line'].create([{
            'order_id': upsell.id,
            'product_id': self.product_no_recurrence.product_variant_id.id,
        }])

        upsell.action_confirm()
        tasks = self.env['project.task'].search(task_domain)
        self.assertEqual(len(tasks), 2, 'Task should only be created on upsell if the product is non-recurring')
        self.assertTrue(self.product_no_recurrence.name in tasks[0].name)

    def test_create_recurring_task_from_template_on_sale_order_confirmation(self):
        """
        Test that confirming a subscription-based sale order with a recurring service product
        creates a recurring task using the specified task template.

        Steps:
            1. Create a recurring task template.
            2. Create a service product linked to the template.
            3. Create a subscription sale order and add the product.
            4. Confirm the sale order.
            5. Assert the task is created with correct recurrence.
        """
        self.project.allow_recurring_tasks = True
        task_template = self.env['project.task'].create({
            'is_template': True,
            'name': 'Recurring Template',
            'project_id': self.project.id,
            'recurring_task': True,
            'repeat_unit': 'week',
            'repeat_type': 'forever',
            'date_deadline': "2023-01-01 00:00:00",
        })

        product_template = self.env['product.template'].create({
            'name': 'Recurring Service Product',
            'type': 'service',
            'recurring_invoice': True,
            'project_id': self.project.id,
            'service_tracking': 'task_global_project',
            'task_template_id': task_template.id,
        })
        product = product_template.product_variant_id

        sale_order = self.env['sale.order'].create({
            'is_subscription': True,
            'plan_id': self.plan_month.id,
            'partner_id': self.partner.id,
        })

        order_line = self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': product.id,
        })

        sale_order.action_confirm()

        self.assertTrue(order_line.task_id.recurring_task, "The task should be marked as recurring.")
        self.assertEqual(order_line.task_id.repeat_unit, 'week', "The repeat unit should be 'week'.")
        self.assertEqual(order_line.task_id.repeat_type, 'forever', "The repeat type should be 'forever'.")
        self.assertEqual(
            order_line.task_id.date_deadline,
            datetime(2023, 1, 1, 0, 0, 0),
            "The task deadline should be 2023-01-01 00:00:00."
        )

    def test_recurring_product_requires_subscription(self):
        """
        Adding a recurring service product on a non-subscription
        sale order must raise a UserError.
        """
        # Create a regular (non-subscription) sale order
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'is_subscription': False,
        })

        # Confirm the order to match real user scenario
        order.action_confirm()

        # Adding a recurring product without a plan must fail
        with self.assertRaisesRegex(
            UserError,
            "Please add a recurring plan on the subscription or remove the recurring product.",
        ):
            order.write({
                'order_line': [(
                    0, 0,
                    {
                        'product_id': self.product_recurrence.product_variant_id.id,
                    }
                )],
            })
