# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    access_token_validity = fields.Integer(string='Default Access Token Validity Duration',
        default=30, config_parameter='hr_contract_salary.access_token_validity')
    employee_salary_simulator_link_validity = fields.Integer(string='Default Salary Configurator Link Validity Duration For Employees',
        default=30, config_parameter='hr_contract_salary.employee_salary_simulator_link_validity')

    _check_access_token_validity = models.Constraint(
        'CHECK(access_token_validity > 0)',
        "The access token validity should be positive.",
    )
    _check_employee_salary_simulator_link_validity = models.Constraint(
        'CHECK(employee_salary_simulator_link_validity > 0)',
        "The salary configurator link validity should be positive.",
    )
