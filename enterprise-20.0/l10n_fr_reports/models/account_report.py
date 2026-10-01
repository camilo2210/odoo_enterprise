from odoo import fields, models


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_accepted_figure_types(self):
        # EXTEND account.report
        return super()._get_accepted_figure_types() | {'datetime_year'}


class AccountReportExpression(models.Model):
    _inherit = 'account.report.expression'

    figure_type = fields.Selection(
        selection_add=[
            ('datetime_year', 'Datetime Year'),
        ],
        ondelete={'datetime_year': 'cascade'},
    )


class AccountReportColumn(models.Model):
    _inherit = 'account.report.column'

    figure_type = fields.Selection(
        selection_add=[
            ('datetime_year', 'Datetime Year'),
        ],
        ondelete={'datetime_year': 'cascade'},
    )
