# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    planning_generation_interval = fields.Integer("Rate Of Shift Generation", required=True, readonly=False, default=6)

    planning_employee_unavailabilities = fields.Selection(
        selection=[
            ('switch', 'Request a replacement'),
            ('unassign', 'Remove themselves from shifts'),
        ],
        string="Shift Changes",
        default='switch',
        required=True,
    )

    planning_self_unassign_days_before = fields.Integer("Days before shift for unassignment", help="Deadline in days for shift unassignment")
    field_service_travel_fees = fields.Boolean("Travel Fees")
    website_planning_field_service = fields.Boolean()

    _planning_self_unassign_days_before_positive = models.Constraint(
        'CHECK(planning_self_unassign_days_before >= 0)',
        "The amount of days before unassignment must be positive or equal to zero.",
    )
