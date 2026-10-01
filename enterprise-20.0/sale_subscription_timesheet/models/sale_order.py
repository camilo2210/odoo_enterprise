from odoo import models
from datetime import timedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _can_deduce_timesheet_range(self):
        """Determine whether a timesheet date range can be inferred from the sale order.

        A date range is considered deducible when sale order:
        - Is a confirmed subscription order, and
        - Contains at least one product delivered through timesheets.

        :rtype: bool
        :return: Whether or not timesheet range can be deduced.
        """
        return (
            self.is_subscription
            and self.state == 'sale'
            and self.order_line.product_id.filtered(
                lambda p: p._is_delivered_timesheet()
            )
        )

    def _get_range_dates(self):
        """Return the start and end dates for the subscription
        order's period to link the timesheets that just lays in
        between this period.

        :return: a start date and end date for the subscription period
        """
        self.ensure_one()

        if self._can_deduce_timesheet_range():
            return (
                self.last_invoice_date or self.start_date,
                self.next_invoice_date + timedelta(days=-1),
            )
        return None, None
