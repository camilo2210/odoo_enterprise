# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PayrollConfigSettings(models.Model):
    _inherit = 'payroll.config.settings'

    l10n_vn_reduced_occupational_accident_rate = fields.Boolean(
        string="Reduced Occupational Accident Rate",
        help="The employer holds a written approval to contribute to the occupational accident and "
             "disease fund at the reduced rate (0.3% instead of 0.5%).")
    l10n_vn_union_fund_rate = fields.Float(
        string="Trade Union Funding Rate (%)", digits='Payroll Rate',
        help="Trade union funding rate approved for the employer, e.g. 1.6 with a reduction approval. "
             "Leave empty to apply the legal rate (2%).")
