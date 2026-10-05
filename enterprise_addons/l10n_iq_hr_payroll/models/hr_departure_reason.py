# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartureReason(models.Model):
    _inherit = "hr.departure.reason"

    l10n_iq_reason_type = fields.Selection([
        ('contract_terminated', "Contract terminated"),
        ('misconduct', "Misconduct"),
    ], default='contract_terminated')
