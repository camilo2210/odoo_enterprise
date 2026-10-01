from odoo import models
from odoo.fields import Domain
from odoo.tools import SQL


class StockIntrastatReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.report.handler'

    def _get_intrastat_report_query(self, report, options, current_groupby, query_params=None, warnings=None, order_by=True):
        query_params.setdefault('intrastat_region_field', []).append(SQL("pos_aic.code"))
        query_params.setdefault('stock_intrastat_join', []).append(SQL("""
            LEFT JOIN pos_order pos_po ON pos_po.account_move = account_move_line.move_id
            LEFT JOIN stock_picking pos_sp ON pos_sp.pos_order_id = pos_po.id
            LEFT JOIN stock_picking_type pos_spt ON pos_spt.id = pos_sp.picking_type_id
            LEFT JOIN stock_warehouse pos_sw ON pos_sw.id = pos_spt.warehouse_id
            LEFT JOIN account_intrastat_code pos_aic ON pos_aic.id = pos_sw.intrastat_region_id
        """))
        return super()._get_intrastat_report_query(report, options, current_groupby, query_params, warnings, order_by)

    def _build_region_code_domain_block(self, region_code):
        region_domain = super()._build_region_code_domain_block(region_code)
        if region_code:
            region_domain = Domain.AND([
                region_domain,
                Domain.OR([
                    [('move_id.pos_order_ids', '=', False)],
                    [('move_id.pos_order_ids.picking_ids', '=', False)],
                    [('move_id.pos_order_ids.picking_ids.picking_type_id', '=', False)],
                    [('move_id.pos_order_ids.picking_ids.picking_type_id.warehouse_id', '=', False)],
                    [('move_id.pos_order_ids.picking_ids.picking_type_id.warehouse_id.intrastat_region_id', '=', False)],
                ])
            ])
        return region_domain

    def _build_intrastat_custom_domain_blocks(self, grouping_key_dict):
        domain_dict = super()._build_intrastat_custom_domain_blocks(grouping_key_dict)

        region_code = grouping_key_dict.get('region_code')
        domain_dict['region_code'] = Domain.OR([
            domain_dict['region_code'],
            [('move_id.pos_order_ids.picking_ids.picking_type_id.warehouse_id.intrastat_region_id.code', '=', region_code)],
        ])

        return domain_dict
