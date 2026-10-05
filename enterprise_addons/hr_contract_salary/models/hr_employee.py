# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    salary_offers_count = fields.Integer(compute='_compute_salary_offers_count', compute_sudo=True)

    def _compute_salary_offers_count(self):
        offers_data = self.env['hr.contract.salary.offer']._read_group(
            domain=[('employee_id', 'in', self.ids), ('is_simulation_offer', '=', False)],
            groupby=['employee_id'],
            aggregates=['__count'])
        mapped_data = {employee.id: count for employee, count in offers_data}
        for employee in self:
            employee.salary_offers_count = mapped_data.get(employee.id, 0)

    def action_show_contract_reviews(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.version",
            "views": [[False, "list"], [False, "form"]],
            "domain": [["origin_version_id", "=", self.version_id.id]],
            "context": {"active_test": False},
            "name": "Contracts Reviews",
        }

    def action_show_offers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_contract_salary.hr_contract_salary_offer_action')
        action['domain'] = [('employee_id', 'in', self.id), ('is_simulation_offer', '=', False)]
        action['context'] = {
            'default_employee_id': self.id,
            'default_employee_version_id': self.version_id.id,
            'is_simulation_offer': True,
        }
        return action

    def action_generate_offer(self):

        offer_validity_period = self.env['ir.config_parameter'].sudo().get_int(
            'hr_contract_salary.employee_salary_simulator_link_validity') or 30
        offer_values = self._get_offer_values()
        offer_values['default_validity_days_count'] = offer_validity_period

        action = self.env['ir.actions.act_window']._for_xml_id('hr_contract_salary.action_hr_offer_new')
        action['domain'] = [('employee_id', 'in', self.id), ('is_simulation_offer', '=', False)]
        action['context'] = {
            'active_model': 'hr.version',
            'default_employee_id': self.id,
            'is_simulation_offer': True,
            **offer_values
        }
        return action

    def _get_offer_values(self):
        self.ensure_one()
        return {
            'default_company_id': self.company_id.id,
            'default_final_yearly_costs': self.final_yearly_costs,
            'default_salary_amount': self.final_yearly_costs,
            'default_structure_type_id': self.structure_type_id,
            'default_budget_type': 'yearly_employer',
            'default_job_title': self.job_id.name,
            'default_employee_job_id':  self.job_id.id,
            'default_department_id': self.department_id.id,
            'default_display_name': _("Offer for %(recipient)s", recipient=self.name),
        }
