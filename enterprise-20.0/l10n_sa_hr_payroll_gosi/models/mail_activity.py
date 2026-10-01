# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    technical_usage = fields.Selection(selection_add=[
        ('l10n_sa_gosi_wage_update', 'GOSI wage update')
    ])
