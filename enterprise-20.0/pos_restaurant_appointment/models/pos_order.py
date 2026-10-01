# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    calendar_event_ids = fields.Many2many(
        'calendar.event',
        string="Calendar Events",
        help="Calendar events associated with this POS order.",
    )
    calendar_event_count = fields.Integer(
        compute='_compute_calendar_event_count',
        string='Calendar Event Count',
        help="Linked Calendar events count for this POS order.",
    )

    @api.depends('calendar_event_ids')
    def _compute_calendar_event_count(self):
        """Compute the number of calendar events linked to each POS order."""
        for order in self:
            order.calendar_event_count = len(order.calendar_event_ids)

    def action_view_calendar_event(self):
        """Open the calendar events linked to this POS order."""
        return {
            **self.env['ir.actions.actions']._for_xml_id('calendar.action_calendar_event'),
            'domain': [('id', 'in', self.calendar_event_ids.ids)],
            'views':  [[False, 'list'], [False, 'form'], [False, 'calendar']],
        }
