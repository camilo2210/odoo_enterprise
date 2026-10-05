from odoo import models
from odoo.tools import SQL


class AccountIntrastatReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.report.handler'

    def _get_intrastat_report_query(self, report, options, current_groupby, query_params=None, warnings=None, order_by=True):
        query_params = {
            **(query_params or {}),
            'extra_conditions': SQL(
                "%s %s",
                query_params.get('extra_conditions', SQL()),
                SQL("""
                    AND (
                        NOT EXISTS (
                            SELECT 1
                              FROM sale_order_line_invoice_rel solam
                             WHERE solam.invoice_line_id = account_move_line.id
                        )
                        OR EXISTS (
                           SELECT 1
                             FROM sale_order_line_invoice_rel solam
                             JOIN sale_order_line sol ON solam.order_line_id = sol.id
                             JOIN sale_order so ON sol.order_id = so.id
                            WHERE solam.invoice_line_id = account_move_line.id
                              AND (
                                sol.is_rental IS NOT TRUE
                                OR so.rental_return_date - so.rental_start_date >= INTERVAL '2 years'
                              )
                        )
                    )
                """)
            ),
        }
        return super()._get_intrastat_report_query(report, options, current_groupby, query_params, warnings, order_by)
