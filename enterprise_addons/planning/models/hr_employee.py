# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import uuid

from psycopg2 import sql

from odoo import fields, models, _, api
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _default_employee_token(self):
        return str(uuid.uuid4())

    default_planning_role_id = fields.Many2one(related='resource_id.default_role_id', readonly=False, groups='hr.group_hr_user',
        write_sequence=25,  # inverse after planning_role_ids, see (test_relation_employee_role_ids_resource_id_role_ids)
        help="Role that will be selected by default when creating a shift for this employee.\n"
             "This role will also have precedence over the other roles of the employee when planning orders.")
    planning_role_ids = fields.Many2many(related='resource_id.role_ids', readonly=False, groups='hr.group_hr_user',
        help="Roles that the employee can fill in. When creating a shift for this employee, only the shift templates for these roles will be displayed.\n"
             "Similarly, only the open shifts available for these roles will be sent to the employee when the schedule is published.\n"
             "Additionally, the employee will only be assigned orders for these roles (with the default planning role having precedence over the other ones).\n"
             "Leave empty for the employee to be assigned shifts regardless of the role.")
    employee_token = fields.Char('Security Token', default=_default_employee_token, groups='hr.group_hr_user',
                                 copy=False, readonly=True, export_string_translation=False, init_storage='_init_column_employee_token')
    has_slots = fields.Boolean(compute='_compute_has_slots')

    _employee_token_unique = models.Constraint(
        'unique(employee_token)',
        "Error: each employee token must be unique",
    )

    @api.depends('job_title')
    @api.depends_context('show_job_title', 'formatted_display_name')
    def _compute_display_name(self):
        if not self.env.context.get('show_job_title'):
            return super()._compute_display_name()
        for employee in self:
            if employee.sudo().job_id:
                if self.env.context.get('formatted_display_name'):
                    employee.display_name = f"{employee.name} \t --({employee.sudo().job_id.name})--"
                else:
                    employee.display_name = f"{employee.name} ({employee.sudo().job_id.name})"
            else:
                employee.display_name = employee.name

    def _init_column_employee_token(self):
        # to avoid generating a single default employee_token when installing the module,
        # we need to set the default row by row for this column
        _logger.debug("Table '%s': setting default value of new column employee_token to unique values for each row", self._table)
        self.env.cr.execute(SQL("SELECT id FROM %s WHERE employee_token IS NULL", SQL.identifier(self._table)))
        acc_ids = self.env.cr.dictfetchall()
        values_args = [(acc_id['id'], self._default_employee_token()) for acc_id in acc_ids]
        query = sql.SQL("""
            UPDATE {table}
            SET employee_token = vals.token
            FROM (VALUES %s) AS vals(id, token)
            WHERE {table}.id = vals.id
        """).format(table=sql.Identifier(self._table))
        self.env.cr.execute_values(query, values_args)

    def _planning_get_url(self, date_start, date_end):
        result = {}
        for employee in self:
            if employee.user_id and not employee.user_id._is_portal():
                result[employee.id] = f"/odoo/action-planning.planning_action_open_shift?date_start={date_start}&date_end={date_end}"
        return result

    @api.onchange('default_planning_role_id')
    def _onchange_default_planning_role_id(self):
        self.planning_role_ids |= self.default_planning_role_id

    @api.onchange('planning_role_ids')
    def _onchange_planning_role_ids(self):
        if self.default_planning_role_id.id not in self.planning_role_ids.ids:
            self.default_planning_role_id = self.planning_role_ids[:1]

    def _compute_has_slots(self):
        result = set()
        if self.ids:
            result.update(id_ for [id_] in self.env.execute_query(SQL(
                """ SELECT id
                      FROM hr_employee e
                     WHERE id IN %s
                       AND EXISTS (
                            SELECT 1
                              FROM planning_slot
                              JOIN planning_slot_resource_resource_rel rel
                                ON planning_slot.id = rel.planning_slot_id
                             WHERE rel.resource_resource_id = e.resource_id
                             LIMIT 1
                           )
                """,
                tuple(self.ids),
            )))

        for employee in self:
            employee.has_slots = employee._origin.id in result

    def action_view_planning(self):
        action = self.env["ir.actions.actions"]._for_xml_id("planning.planning_action_schedule_by_resource")
        action.update({
            'name': _('View Planning'),
            'domain': [('resource_ids', 'in', self.resource_id.ids)],
            'context': {
                'search_default_group_by_resource': True,
                'filter_resource_ids': self.resource_id.ids,
                'default_resource_ids': self.resource_id.ids,
            }
        })
        return action
