# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class L10nChHrContractWage(models.Model):
    _name = 'l10n.ch.hr.contract.wage'
    _description = 'Monthly Recurring Wages'

    version_id = fields.Many2one('hr.version', required=True, ondelete="cascade")
    employee_id = fields.Many2one(related='version_id.employee_id', store=True)
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Wage Type', required=True, domain=lambda self: [('struct_ids', 'in', [self.env.ref('l10n_ch_hr_payroll.hr_payroll_structure_ch_elm').id]), ('input_usage_payslip', '=', True)])
    description = fields.Char(string="Additional Description", help="The description you want to display on the payslip")
    amount = fields.Float(digits='Payroll Rate')
    currency_id = fields.Many2one(related='version_id.currency_id')
    # Optional if we want a one time payment
    date_start = fields.Date(string="Pay Period", help="The wage type payment will be applied in the month covering this date")
    type = fields.Selection(selection=([('one_time', 'One Time Payment'),
                                        ('recurrent', 'Recurrent Payment')]), compute="_compute_type", store=True)

    uom = fields.Selection(string="Unit", selection=[('currency', 'CHF'),
                                                     ('hours', 'Hours'),
                                                     ('percentage', '%')], compute="_compute_uom", store=True)

    @api.depends('version_id', 'description', 'date_start')
    def _compute_display_name(self):
        for wage in self:
            uom = "CHF"
            if wage.uom == 'hours':
                uom = _("Hours")
            elif wage.uom == "percentage":
                uom = "%"
            wage.display_name = f"{wage.salary_rule_id.name} - {wage.amount} {uom} - {wage.employee_id.name}"

    @api.depends("date_start")
    def _compute_type(self):
        for wage in self:
            if wage.date_start:
                wage.type = 'one_time'
            else:
                wage.type = 'recurrent'

    @api.depends('salary_rule_id')
    def _compute_uom(self):
        for wage in self:
            code = wage.salary_rule_id.code
            if code in ["WT_Hours", "WT_Overtime", "WT_Overtime_125", 'WT_Lesson_input', 'WT_on_call_125', 'WT_night_110', 'WT_Overtime_150', 'WT_Overtime_200']:
                wage.uom = "hours"
            elif code and code.startswith('AVS.GENERIC'):
                wage.uom = "percentage"
            else:
                wage.uom = "currency"
