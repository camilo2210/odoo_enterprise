# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.models import TableSQL
from odoo.tools import SQL


class MrpReport(models.Model):
    _inherit = 'mrp.report'

    total_cost = fields.Monetary(help="Total cost of manufacturing order (component + operation costs + subcontracting cost)")
    subcontracting_cost = fields.Monetary(
        "Total Subcontracting Cost", readonly=True,
        help="Total cost of subcontracting for manufacturing order")
    unit_subcontracting_cost = fields.Monetary(
        "Total Subcontracting Cost / Unit", readonly=True, aggregator="avg",
        help="Subcontracting cost per unit produced (in product UoM) of manufacturing order")

    def _total_cost(self, table: TableSQL):
        return SQL("(%s + %s)", super()._total_cost(table), self._get_sub_cost(table).total)

    def _select_dict(self, table: TableSQL):
        sub_cost = self._get_sub_cost(table)
        byproducts_cost_share = self._get_byproducts_cost_share(table)
        total_qty_produced = self._get_total_qty_produced(table)
        return super()._select_dict(table) | {
            'subcontracting_cost': SQL("%s * %s", sub_cost.total, table.consolidation_rate),
            'unit_subcontracting_cost': SQL("%s * (1 - %s) / %s * %s", sub_cost.total, byproducts_cost_share.byproduct_cost_share, total_qty_produced.product_qty, table.consolidation_rate),
        }

    def _get_sub_cost(self, main_table):
        return self._left_join('sub_cost', SQL("""(
                SELECT
                    mo.id AS mo_id,
                    COALESCE(SUM(sm_sub_total.total), 0.0) AS total
                FROM mrp_production AS mo
                LEFT JOIN (
                    SELECT
                        sm_fin.production_id,
                        sm_fin.product_id,
                        sm_sub.price_unit * sm_fin.product_qty AS total
                    FROM stock_move AS sm_fin
                    LEFT JOIN stock_move_move_rel AS sm_rel ON sm_rel.move_orig_id = sm_fin.id
                    LEFT JOIN stock_move AS sm_sub ON sm_rel.move_dest_id = sm_sub.id
                    WHERE sm_sub.is_subcontract IS TRUE
                    GROUP BY sm_fin.production_id, sm_fin.product_id, sm_sub.price_unit, sm_fin.product_qty
                ) AS sm_sub_total ON sm_sub_total.production_id = mo.id AND sm_sub_total.product_id = mo.product_id
                GROUP BY mo.id
        )"""), main_table)
