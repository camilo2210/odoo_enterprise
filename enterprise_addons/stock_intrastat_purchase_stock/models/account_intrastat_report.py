from odoo import models
from odoo.fields import Domain
from odoo.tools import SQL


class StockIntrastatReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.report.handler'

    def _get_intrastat_report_query(self, report, options, current_groupby, query_params=None, warnings=None, order_by=True):
        query_params.setdefault('intrastat_region_field', []).append(SQL("paic.code"))
        query_params.setdefault('stock_intrastat_join', []).append(SQL("""
            LEFT JOIN purchase_order_line pol ON pol.id = account_move_line.purchase_line_id
            LEFT JOIN stock_move psm ON psm.purchase_line_id = pol.id
            LEFT JOIN stock_warehouse psw ON psw.id = psm.warehouse_id
            LEFT JOIN account_intrastat_code paic ON paic.id = psw.intrastat_region_id
        """))
        return super()._get_intrastat_report_query(report, options, current_groupby, query_params, warnings, order_by)

    def _build_region_code_domain_block(self, region_code):
        region_domain = super()._build_region_code_domain_block(region_code)
        if region_code:
            region_domain = Domain.AND([
                region_domain,
                Domain.OR([
                    [('purchase_line_id', '=', False)],
                    [('purchase_line_id.move_ids', '=', False)],
                    [('purchase_line_id.move_ids.warehouse_id', '=', False)],
                    [('purchase_line_id.move_ids.warehouse_id.intrastat_region_id', '=', False)],
                ])
            ])
        return region_domain

    def _build_intrastat_custom_domain_blocks(self, grouping_key_dict):
        domain_dict = super()._build_intrastat_custom_domain_blocks(grouping_key_dict)

        region_code = grouping_key_dict.get('region_code')
        domain_dict['region_code'] = Domain.OR([
            domain_dict['region_code'],
            [('purchase_line_id.move_ids.warehouse_id.intrastat_region_id.code', '=', region_code)],
        ])

        return domain_dict
