# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class EditBillableTimeTarget(models.Model):
    _inherit = "edit.billable.time.target"

    leave_date_to = fields.Date(related='employee_id.leave_date_to', compute_sudo=True)
