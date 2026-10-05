# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_be_reason_code = fields.Integer("Reason Code (BE)")
