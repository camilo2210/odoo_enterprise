# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.tools import format_date, format_time


class AppointmentType(models.Model):
    _inherit = "appointment.type"

    @api.model
    def _product_id_domain(self):
        return [
            ('type', '=', 'service'),
            ('sale_ok', '=', True),
            ('service_tracking', 'not in', self.env['product.template']._service_tracking_blacklist()),
        ]

    has_payment_step = fields.Boolean("Up-front Payment", help="Require visitors to pay to confirm their booking")
    product_id = fields.Many2one(
        'product.product', string="Booking Product",
        domain=_product_id_domain,
        tracking=True)
    product_currency_id = fields.Many2one(related='product_id.currency_id')
    product_lst_price = fields.Float(related='product_id.lst_price')

    _check_product_and_payment_step = models.Constraint(
        'CHECK(has_payment_step IS NULL OR NOT has_payment_step OR product_id IS NOT NULL)',
        "Activating the payment step requires a product",
    )

    def _get_booking_multiline_description(self, start, stop, user, tz):
        """ Utility method returning a multiline description of the booking, including the
            time range and the name of the user argument if set.
            e.g.: '''Dental Care with Mitchell Admin
                     28/11/2025 at 10:00:00AM to 28/11/2025 at 11:00:00AM (Europe/Brussels)'''
        """
        env_tz = self.with_context(tz=tz).env
        common_args = {
            'name': self.name,
            'date_start': format_date(env_tz, start),
            'time_start': format_time(env_tz, start, tz=tz),
            'date_end': format_date(env_tz, stop),
            'time_end': format_time(env_tz, stop, tz=tz),
            'timezone': tz,
        }
        if user:
            return _(
                "%(name)s with %(user_name)s\n%(date_start)s at %(time_start)s to %(date_end)s at %(time_end)s (%(timezone)s)",
                user_name=user.display_name, **common_args
            )
        return _(
            "%(name)s\n%(date_start)s at %(time_start)s to %(date_end)s at %(time_end)s (%(timezone)s)",
            **common_args
        )
