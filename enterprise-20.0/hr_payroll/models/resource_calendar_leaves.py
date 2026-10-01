# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    work_entry_type_id = fields.Many2one(index='btree_not_null')
    category_options_ids = fields.Many2many('hr.salary.rule.category', string="Payroll Options", groups="hr_payroll.group_hr_payroll_user",
        domain="[('optional_on_work_entry_type_ids', 'in', work_entry_type_id)]")
    options_on_work_entry_type_ids = fields.Many2many(related='work_entry_type_id.optional_category_ids', groups="hr_payroll.group_hr_payroll_user")
