# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Command


class HrTimeRule(models.Model):
    _inherit = 'hr.time.rule'

    def _get_output_attendance_vals(self, employee, check_in, check_out, source_attendance=None, accumulated_pp=frozenset()):
        vals = super()._get_output_attendance_vals(
            employee, check_in, check_out,
            source_attendance=source_attendance, accumulated_pp=accumulated_pp,
        )
        if accumulated_pp:
            vals['category_options_ids'] = [Command.set(list(accumulated_pp))]
        return vals
