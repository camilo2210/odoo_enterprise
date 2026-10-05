# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

from datetime import datetime


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _merge_method(self, destination, source):
        tickets = destination + source
        status_list = self.env['helpdesk.sla.status']

        # datetime.max is in case one of the merged ticket is in a stage with "sla_id.exclude_stage_ids"
        for status in tickets.mapped('sla_status_ids').grouped('sla_id').values():
            status_list += min(status, key=lambda s: s.deadline or datetime.max)

        self.env['data_merge.record']._update_foreign_keys(destination, source)
        destination.update({'sla_status_ids': status_list, 'sla_ids': status_list.mapped('sla_id')})

        # To avoid creating a `data_merge_helpdesk_sale_timesheet` bridge module, we check if the timesheet fields are available.
        # If necessary, we ensure that the timesheet so line is updated according to the destination ticket's value.
        # _compute_so_line can't update the value because the cache is invalidated too late in _update_foreign_keys and the recompute don't have proper values
        if hasattr(destination, 'sale_line_id') and hasattr(destination, 'timesheet_ids'):
            ts_to_edit = destination.timesheet_ids.filtered(lambda ts: not ts.is_so_line_edited and ts._is_not_billed() and not ts.validated and ts.so_line != destination.sale_line_id)
            ts_to_edit.write({"so_line": destination.sale_line_id.id})

        return {'post_merge': True, 'log_chatter': True}
