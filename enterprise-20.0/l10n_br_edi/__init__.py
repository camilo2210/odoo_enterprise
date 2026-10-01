# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import wizard


def _l10n_br_res_company_post_init(env):
    for company in env['res.company'].search([('chart_template', '=', 'br')]):
        ChartTemplate = env['account.chart.template'].with_company(company)
        ChartTemplate._load_data({
            'res.company': ChartTemplate._get_br_res_company_l10n_br_is_icbs(company.chart_template),
        })
