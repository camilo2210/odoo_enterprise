# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_uz_is_severance_paid = fields.Boolean(string="Severance Paid", default=True, help="If enabled, the departure reason entitles the employee to severance pay")
