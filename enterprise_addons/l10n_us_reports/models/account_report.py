from odoo import models


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_static_line_dict(self, options, line, all_column_groups_expression_totals, parent_id=None):
        ''' Override to add classes to specific lines'''
        rslt = super()._get_static_line_dict(options, line, all_column_groups_expression_totals, parent_id)
        xmlids = (
            'l10n_us_reports.pl_gross_profit',
            'l10n_us_reports.pl_net_operating_income',
            'l10n_us_reports.pl_net_other_income',
        )
        lines_to_bold = [
            self.env['ir.model.data']._xmlid_to_res_id(xmlid)
            for xmlid in xmlids
        ]
        if line.id in lines_to_bold:
            rslt.css_class = ((rslt.css_class or '') + ' fw-bold').strip()
        return rslt
