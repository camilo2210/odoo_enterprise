# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class HrPayrollSetScheduleWizard(models.TransientModel):
    _name = 'hr.payroll.set.schedule.wizard'
    _description = "HR Payroll Set Schedule Wizard"

    country_code = fields.Char(default=lambda self: self.env.company.country_code, readonly=True)

    first_payrun_date = fields.Date(
        "First Payrun Month",
        help="When do you plan on starting Odoo for your Payroll?",
        required=True,
    )
    payroll_closing_date = fields.Selection(
        selection=lambda self: self.env.company._selection_payroll_closing_date(),
        string="Closing Date",
        help="For monthly pay only, we'll show warnings and send the reminders based on this schedule.",
        required=True,
    )
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        domain="['|', ('company_id', '=', False), ('company_id', '=', allowed_company_ids[0])]",
        required=True,
        default=lambda self: self.env.company.resource_calendar_id,
    )
    hide_resource_calendar_id = fields.Boolean(compute='_compute_hide_resource_calendar_id')

    @api.depends_context('company')
    def _compute_hide_resource_calendar_id(self):
        for wizard in self:
            wizard.hide_resource_calendar_id = bool(self.env.company.resource_calendar_id)

    def action_save(self):
        self.ensure_one()
        self.env.company.write({
            'first_payrun_date': self.first_payrun_date,
            'payroll_closing_date': self.payroll_closing_date,
            'resource_calendar_id': self.resource_calendar_id,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }
