# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists, SQL


class PlanningAnalysisReport(models.Model):
    _name = 'planning.analysis.report'
    _description = "Planning Analysis Report"
    _auto = False

    allocated_hours = fields.Float("Allocated Time", readonly=True)
    allocated_percentage = fields.Float("Allocated Time (%)", readonly=True, aggregator="avg")
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    department_id = fields.Many2one("hr.department", readonly=True)
    employee_ids = fields.Many2many("hr.employee", string="Employees", related='slot_id.employee_ids', readonly=True)
    end_datetime = fields.Datetime("End Date", readonly=True)
    manager_id = fields.Many2one("hr.employee", string="Manager", readonly=True)
    name = fields.Text("Note", readonly=True)
    publication_warning = fields.Boolean(
        "Modified Since Last Publication", readonly=True,
        help="If checked, it means that the shift contains has changed since its last publish.")
    recurrency_id = fields.Many2one("planning.recurrency", readonly=True)
    resource_ids = fields.Many2many("resource.resource", string="Resources", relation="planning_slot_resource_resource_rel", column1="planning_slot_id", column2="resource_resource_id", readonly=True)
    role_id = fields.Many2one("planning.role", string="Role", readonly=True)
    start_datetime = fields.Datetime("Start Date", readonly=True)
    state = fields.Selection([
        ("1_draft", "Draft"),
        ("2_published", "Scheduled"),
    ], string="Status", readonly=True)
    user_ids = fields.Many2many("res.users", related="slot_id.user_ids", string="User", readonly=True)
    slot_id = fields.Many2one("planning.slot", string="Planning Slot", readonly=True)
    switch_employee_ids = fields.Many2many('hr.employee', 'planning_slot_switch_hr_employee_rel', column1='planning_slot_id', column2='hr_employee_id', readonly=True)

    @property
    def _table_sql(self):
        return SQL("(%s %s %s %s)", self._select(), self._from(), self._join(), self._group_by())

    @api.model
    def _select(self):
        return SQL("""
            SELECT
                S.id AS id,
                S.id AS slot_id,
                S.allocated_hours AS allocated_hours,
                S.allocated_percentage AS allocated_percentage,
                S.company_id AS company_id,
                S.department_id AS department_id,
                S.end_datetime AS end_datetime,
                S.manager_id AS manager_id,
                S.name AS name,
                S.publication_warning AS publication_warning,
                S.role_id AS role_id,
                S.recurrency_id AS recurrency_id,
                S.start_datetime AS start_datetime,
                S.state AS state
        """)

    @api.model
    def _from(self):
        return SQL("""
            FROM planning_slot S
        """)

    @api.model
    def _join(self):
        return SQL()

    @api.model
    def _group_by(self):
        return SQL("""
            GROUP BY S.id,
                     S.allocated_hours,
                     S.allocated_percentage,
                     S.company_id,
                     S.end_datetime,
                     S.name,
                     S.publication_warning,
                     S.role_id,
                     S.recurrency_id,
                     S.start_datetime,
                     S.state
        """)

    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""CREATE or REPLACE VIEW %s as (%s)""", SQL.identifier(self._table), self._table_sql))
