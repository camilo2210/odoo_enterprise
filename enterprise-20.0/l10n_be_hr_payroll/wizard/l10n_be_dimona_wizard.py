# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nBeDimonaWizard(models.TransientModel):
    _name = 'l10n.be.dimona.wizard'
    _description = 'Dimona Wizard'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    version_id = fields.Many2one(
        'hr.version', string='Employee Record', compute='_compute_version_id', store=True, readonly=False,
        domain="[('employee_id', '=', employee_id)]")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', default=lambda self: self.env.context.get('active_id'))
    employee_birthday = fields.Date(related='employee_id.birthday')
    contract_date_start = fields.Date(related='version_id.contract_date_start')
    contract_date_end = fields.Date(related='version_id.contract_date_end')
    contract_is_student = fields.Boolean(compute='_compute_contract_is_student')
    contract_wage_type = fields.Selection(related='version_id.wage_type')
    contract_country_code = fields.Char(related='version_id.country_code')
    contract_planned_hours = fields.Integer(related='version_id.l10n_be_dimona_planned_hours')
    without_niss = fields.Boolean(string="Employee Without NISS")

    declaration_type = fields.Selection(
        selection=[
            ('in', 'Register employee entrance'),
            ('out', 'Register employee departure'),
            ('update', 'Update employee information'),
            ('cancel', 'Cancel employee declaration')
        ], default='in')

    @api.depends('employee_id')
    def _compute_version_id(self):
        for wizard in self:
            wizard.version_id = wizard.employee_id.version_id

    @api.depends('version_id.l10n_be_dimona_category')
    def _compute_contract_is_student(self):
        for wizard in self:
            wizard.contract_is_student = wizard.version_id.l10n_be_dimona_category and wizard.version_id.l10n_be_dimona_category == 'stu'

    def action_open_declaration(self):
        if self.env.company.country_id.code != "BE":
            raise UserError(self.env._('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        if self.env.company._l10n_be_dimona_can_declare():
            return self.env['ir.actions.actions']._for_xml_id('l10n_be_hr_payroll.l10n_be_dimona_wizard_action')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Dimona"),
            'res_model': 'l10n.be.dimona.manual.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def submit_declaration(self):
        self.ensure_one()
        validation_action = None
        if not self.version_id:
            raise UserError(_('There is no contract defined on the employee form.'))
        if self.declaration_type == 'in':
            validation_action = self.version_id._action_open_dimona(foreigner=self.without_niss)
        elif self.declaration_type == 'out':
            self.version_id._action_close_dimona()
        elif self.declaration_type == 'update':
            validation_action = self.version_id._action_update_dimona()
        elif self.declaration_type == 'cancel':
            self.version_id._action_cancel_dimona()
        if validation_action:
            return validation_action
        return {
            'name': self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': self.employee_id.id,
            'views': [(False, 'form')],
            'context': {'version_id': self.version_id.id}
        }
