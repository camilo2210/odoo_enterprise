# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain

from odoo.addons.resource.models.utils import filter_map_domain


class ProjectTask(models.Model):
    _inherit = "project.task"

    def _get_additional_users(self, domain):
        users = super()._get_additional_users(domain)

        def _map_condition(condition):
            if condition.field_expr == 'user_skill_ids':
                return Domain('name', condition.operator, condition.value)
            return None

        skill_search_domain = filter_map_domain(domain, _map_condition)
        if not skill_search_domain:
            return users
        skill_ids = self.env['hr.skill']._search(skill_search_domain)
        user_skill_read_group = self.env['hr.employee.skill'].sudo()._read_group(
            [('skill_id', 'in', skill_ids)],
            [],
            ['employee_id:array_agg'],
        )
        matching_employee_ids = user_skill_read_group[0][0]
        return self.env['res.users'].search([('employee_id', 'in', matching_employee_ids)])
