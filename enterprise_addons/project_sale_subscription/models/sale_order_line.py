# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _compute_product_updatable(self):
        temporal_lines = self.filtered('recurring_invoice')
        super(SaleOrderLine, self - temporal_lines)._compute_product_updatable()
        temporal_lines.product_updatable = True

    def _timesheet_service_generation(self):
        super(SaleOrderLine, self.filtered(
            lambda sol: sol._can_generate_service()
        ))._timesheet_service_generation()

    def _can_generate_service(self):
        return self.order_id._can_generate_service() or not self.recurring_invoice

    def _timesheet_create_task(self, project):
        order = self.order_id
        task = super()._timesheet_create_task(project)
        # Recurrence cannot be configured for recurring products without a subscription plan.
        if not order.plan_id and self.product_id.recurring_invoice:
            return task
        # if the product is not recurrent or the project doesn't allow recurring tasks, we don't bother
        if not self.product_id.recurring_invoice or not project.allow_recurring_tasks:
            return task

        task_template_id = self.product_id.task_template_id
        if task_template_id.recurrence_id:
            task.date_deadline = task_template_id.date_deadline
            recurrence = self.env['project.task.recurrence'].create({
                'task_ids': task.ids,
                'repeat_interval': task_template_id.repeat_interval,
                'repeat_type': task_template_id.repeat_type,
                'repeat_unit': task_template_id.repeat_unit,
                'repeat_until': task_template_id.repeat_until,
            })
            task.write({
                'recurring_task': True,
                'recurrence_id': recurrence.id,
            })
        return task

    def _get_product_from_sol_name_domain(self, product_name):
        return Domain.AND([
            super()._get_product_from_sol_name_domain(product_name),
            [("recurring_invoice", "=", False)],
        ])
