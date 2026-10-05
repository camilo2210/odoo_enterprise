# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.exceptions import UserError


class ExecutiveSummaryCustomHandler(models.AbstractModel):
    _name = 'account.executive.summary.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Executive Summary Custom Handler'

    def _report_engine_executive_summary_ndays(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        if current_groupby:
            raise UserError(self.env._("NDays expressions of executive summary report don't support the 'group by' feature."))

        date_to = fields.Date.from_string(options['date']['date_to'])
        # in 'single' date mode, uses the company's fiscal-year start date
        date_from = (
            fields.Date.from_string(options["date"]["date_from"])
            or self.env.company.compute_fiscalyear_dates(date_to)["date_from"]
        )
        return {next(iter(formulas_dict.values())): {'result': (date_to - date_from).days + 1, 'has_sublines': False}}
