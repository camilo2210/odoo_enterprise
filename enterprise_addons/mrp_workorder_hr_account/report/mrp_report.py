# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.models import TableSQL
from odoo.tools import SQL


class MrpReport(models.Model):
    _inherit = 'mrp.report'

    employee_cost = fields.Monetary(
        "Total Employee Cost", readonly=True, groups="mrp.group_mrp_routings",
        help="Total cost of employees for manufacturing order")
    unit_employee_cost = fields.Monetary(
        "Total Employee Cost / Unit", readonly=True, aggregator="avg", groups="mrp.group_mrp_routings",
        help="Employee cost per unit produced (in product UoM) of manufacturing order")
    unit_operation_cost = fields.Monetary(
        "Total Operation Cost / Unit", readonly=True, aggregator="avg", groups="mrp.group_mrp_routings",
        help="Work center and employee cost per unit produced (in product UoM) of manufacturing order")
    operation_cost = fields.Monetary(
        "Total Operation Cost", readonly=True, groups="mrp.group_mrp_routings",
        help="Total work center and employee cost for manufacturing order")
    expected_operation_cost_unit = fields.Monetary(
        "Expected Operation Cost / Unit", readonly=True, aggregator="avg",
        groups="mrp.group_mrp_routings",
        help="Expected work center and employee cost per unit")

    def _total_cost(self, table: TableSQL):
        return SQL("(%s + %s)", super()._total_cost(table), self._get_op_cost(table).total_emp)

    def _select_dict(self, table: TableSQL):
        byproducts_cost_share = self._get_byproducts_cost_share(table)
        total_qty_produced = self._get_total_qty_produced(table)
        op_cost = self._get_op_cost(table)
        product_standard_price = self._get_product_standard_price(table)
        operation = self._get_operation(table)
        mo = self._get_extra_cost(table)
        return super()._select_dict(table) | {
            'employee_cost': SQL("%s * %s", op_cost.total_emp, table.consolidation_rate),
            'unit_employee_cost': SQL("%s * (1 - %s) / %s * %s", op_cost.total_emp, byproducts_cost_share.byproduct_cost_share, total_qty_produced.product_qty, table.consolidation_rate),
            'unit_operation_cost': SQL("(%s + %s) * (1 - %s) / %s * %s", op_cost.total, op_cost.total_emp, byproducts_cost_share.byproduct_cost_share, total_qty_produced.product_qty, table.consolidation_rate),
            'operation_cost': SQL("(%s + %s) * %s", op_cost.total, op_cost.total_emp, table.consolidation_rate),
            'expected_component_cost_unit': SQL("COALESCE(%s, 0)", product_standard_price.value),
            'expected_employee_cost_unit': SQL("COALESCE(%s, 0)", operation.employee_cost),
            'expected_workcenter_cost_unit': SQL("COALESCE(%s, 0)", operation.workcenter_cost),
            'expected_operation_cost_unit': SQL("COALESCE(%s, 0) + COALESCE(%s, 0)", operation.workcenter_cost, operation.employee_cost),
            'expected_total_cost_unit': SQL("COALESCE(%s, 0) + COALESCE(%s, 0) + COALESCE(%s, 0) + COALESCE(%s, 0)", product_standard_price.value, operation.employee_cost, operation.workcenter_cost, mo.extra_cost),
        }

    def _read_group_select(self, table, aggregate_spec):
        if aggregate_spec in ('unit_employee_cost:avg', 'unit_operation_cost:avg'):
            fname, *__ = models.parse_read_group_spec(aggregate_spec)
            sql_field = table[fname]
            sql_qty_produced = table.qty_produced
            return SQL("SUM(%s * %s) / SUM(%s)", sql_field, sql_qty_produced, sql_qty_produced)
        return super()._read_group_select(table, aggregate_spec)

    def _get_op_cost(self, main_table):
        return self._left_join('op_cost', SQL("""(
                SELECT
                    mo_id                                                                    AS mo_id,
                    SUM(op_costs_hour / 60. * op_duration)                                   AS total,
                    SUM(op_duration)                                                         AS total_duration,
                    SUM(emp_costs)                                                           AS total_emp
                FROM (
                    SELECT
                        mo.id AS mo_id,
                        CASE
                            WHEN wo.costs_hour != 0.0 AND wo.costs_hour IS NOT NULL THEN wo.costs_hour
                            ELSE COALESCE(wc.costs_hour, 0.0) END                                       AS op_costs_hour,
                        CASE
                            WHEN wo.duration_expected != 0.0 AND wo.duration_expected IS NOT NULL AND wo.cost_mode = 'estimated'
                            THEN wo.duration_expected
                            ELSE COALESCE(SUM(t.duration), 0.0) END                                     AS op_duration,
                        CASE
                            WHEN wo.duration_expected != 0.0 AND wo.duration_expected IS NOT NULL AND wo.cost_mode = 'estimated'
                            THEN wo.duration_expected / 60. * wo.employee_costs_hour
                            ELSE COALESCE(SUM(t.duration / 60. * t.employee_cost), 0.0) END             AS emp_costs
                    FROM mrp_production AS mo
                    LEFT JOIN mrp_workorder wo ON wo.production_id = mo.id
                    LEFT JOIN mrp_workcenter_productivity t ON t.workorder_id = wo.id
                    LEFT JOIN mrp_workcenter wc ON wc.id = t.workcenter_id
                    WHERE mo.state = 'done'
                    GROUP BY
                        mo.id,
                        wc.costs_hour,
                        wo.id
                    ) AS op_cost_vars
                GROUP BY mo_id
        )"""), main_table)

    def _get_operation(self, main_table):
        return self._left_join('operation', SQL("""(
                SELECT
                    MIN(mo.id)                                                                  AS mo_id,
                    SUM(%(expected_duration)s * wc.costs_hour)                                  AS workcenter_cost,
                    SUM(%(expected_duration)s * wc.employee_costs_hour * op.employee_ratio)     AS employee_cost
                FROM mrp_production                                                             AS mo
                JOIN mrp_bom                                                                    AS bom
                    ON mo.bom_id = bom.id
                JOIN mrp_routing_workcenter                                                     AS op
                    ON op.bom_id = bom.id
                JOIN mrp_workcenter                                                             AS wc
                    ON wc.id = op.workcenter_id
                LEFT JOIN mrp_workcenter_capacity                                               AS cap
                    ON cap.product_id = bom.product_tmpl_id
                    AND cap.workcenter_id = wc.id
                    AND mo.state = 'done'
                GROUP BY mo.id
        )""", expected_duration=self._get_expected_duration()), main_table)

    def _get_expected_duration(self):
        return SQL("""
            (
                (
                    ((%s) * 100 / wc.time_efficiency)
                    + COALESCE(cap.time_start, COALESCE(wc.time_start,0))
                    + COALESCE(cap.time_stop, COALESCE(wc.time_stop,0))
                )
                / 60
            )
        """, self._get_operation_time_cycle())

    def _get_operation_time_cycle(self):
        return SQL("""
            WITH cycle_info AS (
                SELECT
                    SUM(wo.duration)                                            AS total_duration,
                    SUM(
                        COALESCE(
                            CEIL(
                                wo.qty_produced
                                / COALESCE(cap_specific.capacity,cap_generic.capacity,bom.product_qty,1)
                            ),
                            1
                        )
                    )                                                           AS cycle_number
                FROM mrp_workorder                                              AS wo
                JOIN mrp_workcenter                                             AS wc
                    ON wc.id = wo.workcenter_id
                JOIN product_product                                            AS product
                    ON product.id = mo.product_id
                JOIN product_template                                           AS template
                    ON template.id = product.product_tmpl_id
                LEFT JOIN mrp_workcenter_capacity                               AS cap_specific
                    ON cap_specific.workcenter_id = wc.id
                        AND cap_specific.product_id = product.id
                        AND cap_specific.uom_id = template.uom_id
                LEFT JOIN mrp_workcenter_capacity                               AS cap_generic
                    ON cap_generic.workcenter_id = wc.id
                        AND cap_generic.product_id IS NULL
                        AND cap_generic.uom_id = template.uom_id
                WHERE wo.operation_id = op.id
                    AND wo.qty_produced > 0
                    AND wo.state = 'done'
                GROUP BY op.id
            )
            SELECT
                CASE
                    WHEN op.time_mode = 'manual'        THEN op.time_cycle_manual
                    WHEN cycle_info.cycle_number = 0    THEN op.time_cycle_manual
                    ELSE cycle_info.total_duration / cycle_info.cycle_number
                END
            FROM cycle_info
        """)
