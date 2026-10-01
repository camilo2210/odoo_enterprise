# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.models import TableSQL
from odoo.tools import SQL


class MrpReport(models.Model):
    _name = 'mrp.report'
    _description = "Manufacturing Report"
    _rec_name = 'production_id'
    _auto = False
    _order = 'date_finished desc'

    id = fields.Id(string="")
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True, required=True)
    production_id = fields.Many2one('mrp.production', "Manufacturing Order", readonly=True)
    date_finished = fields.Datetime('End Date', readonly=True)
    product_id = fields.Many2one('product.product', "Product", readonly=True)
    total_cost = fields.Monetary(
        "Total Cost", readonly=True,
        help="Total cost of manufacturing order (component + operation costs)")
    extra_cost = fields.Monetary(
        "Extra Cost", readonly=True, help="Additional cost per manufactured unit (e.g. labour, energy, packaging)"
    )
    component_cost = fields.Monetary(
        "Total Component Cost", readonly=True,
        help="Total cost of components for manufacturing order")
    workcenter_cost = fields.Monetary(
        "Total Work Center Cost", readonly=True, groups="mrp.group_mrp_routings",
        help="Total work center cost for manufacturing order")
    duration = fields.Float(
        "Total Duration of Operations", readonly=True, groups="mrp.group_mrp_routings",
        help="Total duration of operations for manufacturing order")

    qty_produced = fields.Float(
        "Quantity Produced", readonly=True,
        help="Total quantity produced in product's UoM")
    qty_demanded = fields.Float(
        "Quantity Demanded", readonly=True,
        help="Total quantity demanded in product's UoM")
    yield_rate = fields.Float(
        "Yield Percentage(%)", readonly=True,
        help="Ratio of quantity produced over quantity demanded")

    # note that unit costs take include subtraction of byproduct cost share
    unit_cost = fields.Monetary(
        "Total Cost / Unit", readonly=True, aggregator="avg",
        help="Cost per unit produced (in product UoM) of manufacturing order")
    unit_component_cost = fields.Monetary(
        "Total Component Cost / Unit", readonly=True, aggregator="avg",
        help="Component cost per unit produced (in product UoM) of manufacturing order")
    unit_workcenter_cost = fields.Monetary(
        "Total Work Center Cost / Unit", readonly=True, aggregator="avg",
        groups="mrp.group_mrp_routings",
        help="Work center cost per unit produced (in product UoM) of manufacturing order")
    unit_duration = fields.Float(
        "Duration of Operations / Unit", readonly=True, aggregator="avg",
        groups="mrp.group_mrp_routings",
        help="Operation duration per unit produced of manufacturing order")

    byproduct_cost = fields.Monetary(
        "By-Products Total Cost", readonly=True,
        groups="mrp.group_mrp_byproducts")

    expected_component_cost_unit = fields.Monetary(
        "Expected Component Cost / Unit", readonly=True, aggregator="avg",
    )
    expected_employee_cost_unit = fields.Monetary(
        "Expected Employee Cost / Unit", readonly=True, aggregator="avg",
        groups="mrp.group_mrp_routings"
    )
    expected_workcenter_cost_unit = fields.Monetary(
        "Expected Work Center Cost / Unit", readonly=True, aggregator="avg",
        groups="mrp.group_mrp_routings"
    )
    expected_total_cost_unit = fields.Monetary(
        "Expected Total Cost / Unit", readonly=True, aggregator="avg",
        groups="mrp.group_mrp_routings"
    )

    def _select_dict_to_list(self, select_dict):
        return [SQL("%s AS %s", select_dict.get(fname, SQL("NULL")), SQL.identifier(fname)) for fname, field in self._fields.items() if field.store]

    def _left_join(self, alias_str, query, main_table):
        alias = TableSQL(alias_str, None, main_table._query)
        main_table._query.add_join('LEFT JOIN', alias, query, SQL("%s = %s", main_table.id, alias.mo_id))
        return alias

    @property
    def _table_sql(self):
        today = fields.Date.context_today(self)
        query = self.env['mrp.production'].with_context(date_to=today)._search([('state', '=', 'done')])
        return query.subselect(*self._select_dict_to_list(self._select_dict(query.table)))

    def _total_cost(self, table: TableSQL):
        mo = self._get_extra_cost(table)
        return SQL("(%s + %s + (%s * %s))", self._get_component_cost(table).total, self._get_workcenter_cost(table).total, mo.extra_cost, mo.product_qty)

    def _extra_cost(self, table: TableSQL):
        mo = self._get_extra_cost(table)
        return SQL("%s * %s", mo.extra_cost, mo.product_qty)

    def _select_dict(self, table: TableSQL):
        total_cost = self._total_cost(table)
        extra_cost = self._extra_cost(table)
        component_cost = self._get_component_cost(table)
        wc_cost = self._get_workcenter_cost(table)
        byproducts_cost_share = self._get_byproducts_cost_share(table)
        total_qty_produced = self._get_total_qty_produced(table)
        return {
            'id': table.id,
            'production_id': table.id,
            'company_id': table.company_id,
            'currency_id': table.company_id.currency_id,
            'date_finished': table.date_finished,
            'product_id': table.product_id,
            'qty_produced': total_qty_produced.product_qty,
            'qty_demanded': total_qty_produced.qty_demanded,
            'yield_rate': SQL("%s / %s * 100", total_qty_produced.product_qty, total_qty_produced.qty_demanded),
            'component_cost': SQL("%s * %s", component_cost.total, table.consolidation_rate),
            'workcenter_cost': SQL("%s * %s", wc_cost.total, table.consolidation_rate),
            'total_cost': SQL("%s * %s", total_cost, table.consolidation_rate),
            'extra_cost': SQL("%s * %s", extra_cost, table.consolidation_rate),
            'duration': wc_cost.total_duration,
            'unit_component_cost': SQL("%s * (1 - %s) / %s * %s", component_cost.total, byproducts_cost_share.byproduct_cost_share, total_qty_produced.product_qty, table.consolidation_rate),
            'unit_workcenter_cost': SQL("%s * (1 - %s) / %s * %s", wc_cost.total, byproducts_cost_share.byproduct_cost_share, total_qty_produced.product_qty, table.consolidation_rate),
            'unit_cost': SQL("%s * (1 - %s) / %s * %s", total_cost, byproducts_cost_share.byproduct_cost_share, total_qty_produced.product_qty, table.consolidation_rate),
            'unit_duration': SQL("%s / %s", wc_cost.total_duration, total_qty_produced.product_qty),
            'byproduct_cost': SQL("%s / %s", total_cost, total_qty_produced.product_qty),
        }

    def _get_extra_cost(self, main_table):
        return self._left_join('bom', SQL("""(
                SELECT
                    mo.id                      AS mo_id,
                    mo.extra_cost         AS extra_cost,
                    mo.product_qty       AS product_qty
                FROM mrp_production AS mo
                LEFT JOIN mrp_bom    AS bom ON bom.id = mo.bom_id
                WHERE mo.state = 'done'
                GROUP BY mo.id, bom.type, bom.extra_cost
        )"""), main_table)

    def _get_product_standard_price(self, main_table):
        query = self.env['mrp.production']._search([('state', '=', 'done')], bypass_access=True)
        table = query.table
        bom_line = table._join('bom_id')._join('bom_line_ids')
        query.groupby = table.id
        return self._left_join('product_standard_price', query.subselect(
            SQL("%s AS mo_id", table.id),
            SQL("SUM(%s * %s / %s) AS value", bom_line.product_id.standard_price, bom_line.product_qty, table.bom_id.product_qty),
        ), main_table)

    def _get_component_cost(self, main_table):
        return self._left_join('component_cost', SQL("""(
                SELECT
                    mo.id                                                                    AS mo_id,
                    SUM(-sm.value)                                                           AS total
                FROM mrp_production AS mo
                LEFT JOIN stock_move AS sm on sm.raw_material_production_id = mo.id
                LEFT JOIN stock_location AS dest_loc ON sm.location_dest_id = dest_loc.id
                WHERE mo.state = 'done'
                    AND (sm.state = 'done' or sm.state IS NULL)
                    AND dest_loc.usage != 'inventory'
                GROUP BY
                    mo.id
        )"""), main_table)

    def _get_workcenter_cost(self, main_table):
        return self._left_join('wc_cost', SQL("""(
                SELECT
                    mo_id                                                                    AS mo_id,
                    SUM(wc_costs_hour / 60. * op_duration)                                   AS total,
                    SUM(op_duration)                                                         AS total_duration
                FROM (
                    SELECT
                        mo.id AS mo_id,
                        CASE
                            WHEN wo.costs_hour != 0.0 AND wo.costs_hour IS NOT NULL THEN wo.costs_hour
                            ELSE COALESCE(wc.costs_hour, 0.0) END                                       AS wc_costs_hour,
                        CASE
                            WHEN wo.duration_expected != 0.0 AND wo.duration_expected IS NOT NULL AND wo.cost_mode = 'estimated'
                            THEN wo.duration_expected
                            ELSE COALESCE(SUM(t.duration), 0.0) END                                     AS op_duration
                    FROM mrp_production AS mo
                    LEFT JOIN mrp_workorder wo ON wo.production_id = mo.id
                    LEFT JOIN mrp_workcenter_productivity t ON t.workorder_id = wo.id
                    LEFT JOIN mrp_workcenter wc ON wc.id = t.workcenter_id
                    WHERE mo.state = 'done'
                    GROUP BY
                        mo.id,
                        wc.costs_hour,
                        wo.id
                    ) AS wc_cost_vars
                GROUP BY mo_id
        )"""), main_table)

    def _get_byproducts_cost_share(self, main_table):
        return self._left_join('byproducts_cost_share', SQL("""(
                SELECT
                    mo.id AS mo_id,
                    COALESCE(SUM(sm.cost_share), 0.0) / 100.0 AS byproduct_cost_share
                FROM stock_move AS sm
                LEFT JOIN mrp_production AS mo ON sm.production_id = mo.id
                LEFT JOIN stock_location AS dest_loc ON sm.location_dest_id = dest_loc.id
                WHERE
                    mo.state = 'done'
                    AND sm.state = 'done'
                    AND sm.quantity != 0
                    AND dest_loc.usage != 'inventory'
                GROUP BY mo.id
        )"""), main_table)

    def _get_total_qty_produced(self, main_table):
        return self._left_join('total_qty_produced', SQL("""(
                SELECT
                    mo.id AS mo_id,
                    mo.name,
                    SUM(sm.quantity * uom.factor / uom_prod.factor) AS product_qty,
                    SUM(sm.product_uom_qty * uom.factor / uom_prod.factor) AS qty_demanded
                FROM stock_move AS sm
                JOIN mrp_production AS mo ON sm.production_id = mo.id
                JOIN uom_uom AS uom ON uom.id = sm.uom_id
                JOIN product_product AS product ON product.id = sm.product_id
                JOIN product_template AS template ON template.id = product.product_tmpl_id
                JOIN uom_uom AS uom_prod ON uom_prod.id = template.uom_id
                LEFT JOIN stock_location AS dest_loc ON sm.location_dest_id = dest_loc.id
                WHERE
                    mo.state = 'done'
                    AND sm.state = 'done'
                    AND sm.quantity != 0
                    AND mo.product_id = sm.product_id
                    AND dest_loc.usage != 'inventory'
                GROUP BY mo.id
        )"""), main_table)

    def _read_group_select(self, table, aggregate_spec):
        if aggregate_spec in ('unit_cost:avg', 'unit_component_cost:avg', 'unit_workcenter_cost:avg', 'unit_duration:avg'):
            # Make a weigthed average instead of simple average for these fields
            fname, *__ = models.parse_read_group_spec(aggregate_spec)
            sql_field = table[fname]
            sql_qty_produced = table.qty_produced
            return SQL("SUM(%s * %s) / SUM(%s)", sql_field, sql_qty_produced, sql_qty_produced)
        if aggregate_spec == 'yield_rate:sum':
            sql_qty_produced = table.qty_produced
            sql_qty_demanded = table.qty_demanded
            return SQL("SUM(%s) / SUM(%s) * 100", sql_qty_produced, sql_qty_demanded)
        return super()._read_group_select(table, aggregate_spec)
