# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('br', 'res.company')
    def _get_br_res_company_extract(self):
        return {
            self.env.company.id: {
                'extract_single_line_per_tax': False,
            }
        }
