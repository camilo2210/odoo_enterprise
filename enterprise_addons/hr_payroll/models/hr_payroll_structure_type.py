# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'
    _order = 'sequence, id'

    def _get_selection_schedule_pay(self):
        return [
            ('annually', self.env._('year')),
            ('semi-annually', self.env._('half-year')),
            ('quarterly', self.env._('quarter')),
            ('bi-monthly', self.env._('2 months')),
            ('monthly', self.env._('month')),
            ('semi-monthly', self.env._('half-month')),
            ('bi-weekly', self.env._('2 weeks')),
            ('weekly', self.env._('week')),
            ('daily', self.env._('day')),
        ]

    def _default_work_entry_type_id(self):
        country_code = self.env.company.country_code
        attendance = self.env['hr.work.entry.type'].search([
            ('code', '=', '002.00'),
            ('country_code', '=', country_code),
        ], limit=1)
        return attendance or self.env.ref('hr_work_entry.generic_work_entry_type_attendance', raise_if_not_found=False)

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    name = fields.Char('Structure Type', required=True, translate=True)
    default_schedule_pay = fields.Selection(
        selection=lambda self: self._get_selection_schedule_pay(), string='Scheduled Pay', default='monthly',
        help="Defines the frequency of the wage payment.")
    struct_ids = fields.One2many('hr.payroll.structure', 'type_id', string="Structures")
    default_struct_id = fields.Many2one('hr.payroll.structure', string="Pay Structure")
    default_work_entry_type_id = fields.Many2one(
        'hr.work.entry.type',
        string="Time Type", help="Time type for regular attendances.",
        required=True,
        default=_default_work_entry_type_id,
        domain="[('id', 'in', allowed_work_entry_type_ids)]")
    allowed_work_entry_type_ids = fields.Many2many(
        'hr.work.entry.type', compute='_compute_allowed_work_entry_type_ids')
    wage_type = fields.Selection([
        ('monthly', 'Fixed Wage'),
        ('hourly', 'Hourly Wage')
    ], string="Wage Type", default='monthly', required=True)
    struct_type_count = fields.Integer(compute='_compute_struct_type_count', string='Structure Type Count')
    salary_benefits_ids = fields.One2many('hr.contract.salary.benefit', 'structure_type_id')

    def _compute_struct_type_count(self):
        for structure_type in self:
            structure_type.struct_type_count = len(structure_type.struct_ids)

    def _check_country(self, vals):
        country_id = vals.get('country_id')
        if country_id and country_id not in self.env.companies.mapped('country_id').ids:
            raise UserError(_('You should also be logged into a company in %s to set this country.', self.env['res.country'].browse(country_id).name))

    def write(self, vals):
        if self.env.context.get('payroll_check_country'):
            self._check_country(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('payroll_check_country'):
            for vals in vals_list:
                self._check_country(vals)
        return super().create(vals_list)

    @api.depends('country_id')
    def _compute_allowed_work_entry_type_ids(self):
        for structure_type in self:
            country = structure_type.country_id
            if not country or not self.env['hr.work.entry.type'].search_count([('country_id', '=', country.id)], limit=1):
                domain = [('country_id', '=', False)]
            else:
                domain = [('country_id', '=', country.id)]
            structure_type.allowed_work_entry_type_ids = self.env['hr.work.entry.type'].search(domain)
