# Part of Odoo. See LICENSE file for full copyright and licensing details.

from calendar import monthrange
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class L10nSaDisciplinaryAction(models.Model):
    _name = "l10n.sa.disciplinary.action"
    _description = "Disciplinary Action"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    state = fields.Selection(
        string='Status',
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
        ],
        default='draft',
        required=True,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True, domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    payslip_id = fields.Many2one(
        'hr.payslip', string="Related Payslip", readonly=True, copy=False
    )
    payslip_state = fields.Selection(related='payslip_id.state', string='Payslip State', tracking=True)
    action_type = fields.Selection(
        selection=[
            ('warning', 'Warning'),
            ('deduction', 'Deduction'),
            ('other', 'Other')
        ],
        string='Action Type', required=True,
    )
    amount_based_on = fields.Selection(
        selection=[
            ('daily_wage_percentage', '% of Daily Wage'),
            ('monthly_wage_percentage', '% of Monthly Wage'),
            ('custom_amount', 'Custom Amount'),
        ],
        string='Amount Based on',
    )
    amount_base_basic = fields.Boolean(string='Basic')
    amount_base_housing = fields.Boolean(string='Housing Allowance')
    amount_base_transportation = fields.Boolean(string='Transportation Allowance')
    amount_base_other = fields.Boolean(string='Other Allowances')
    daily_wage_based_on = fields.Selection(
        selection=[
            ('calendar_days', 'Calendar Days'),
            ('thirty_days', 'Thirty Days'),
            ('working_days', 'Working Days'),
        ],
        string='Daily Wage Based on',
    )
    amount = fields.Float()
    percentage = fields.Float(string='Percentage')

    _check_percentage = models.Constraint(
        'CHECK(percentage BETWEEN 0 AND 1.0)',
        "Percentage must be between 0% and 100%",
    )

    @api.depends('employee_id', 'date')
    def _compute_display_name(self):
        for action in self:
            action.display_name = self.env._('Disciplinary Action for %(emp)s - %(date)s', emp=action.employee_id.display_name, date=action.date)

    @api.onchange('action_type')
    def _onchange_action_type(self):
        """Clear dependent fields when action_type changes"""
        if self.action_type != 'deduction':
            self.amount_based_on = False

    @api.onchange('amount_based_on')
    def _onchange_amount_based_on(self):
        """Clear dependent fields when amount_based_on changes"""
        if self.amount_based_on != 'daily_wage_percentage':
            self.daily_wage_based_on = False
        if self.amount_based_on != 'custom_amount':
            self.amount = 0.0
        if self.amount_based_on not in ['daily_wage_percentage', 'monthly_wage_percentage']:
            self.amount_base_basic = False
            self.amount_base_housing = False
            self.amount_base_transportation = False
            self.amount_base_other = False
            self.percentage = 0.0

    def action_approve(self):
        for action in self:
            if action.action_type == 'warning':
                action.activity_schedule(
                        'l10n_sa_hr_payroll.mail_activity_data_l10n_sa_disciplinary_action_warning_mail',
                        date_deadline=fields.Date.context_today(self) + relativedelta(days=3),
                        summary=self.env._('Disciplinary Warning to Send'),
                        note=self.env._('A disciplinary warning should be sent to %s',
                                action.employee_id._get_html_link()),
                        user_id=action.employee_id.version_id.hr_responsible_id.id or self.env.ref('base.user_admin').id)
            elif action.action_type == 'deduction':
                if action.amount_based_on in ['daily_wage_percentage', 'monthly_wage_percentage']:
                    if float_compare(action.percentage, 0, precision_digits=2) == 0:
                        raise UserError(self.env._("You cannot add a 0% deduction!"))
                    if not (
                        action.amount_base_basic
                        or action.amount_base_housing
                        or action.amount_base_transportation
                        or action.amount_base_basic
                    ):
                        raise UserError(self.env._("Please select at least one category the amount should be based on!"))

            action.state = 'approved'

    def action_set_to_draft(self):
        for action in self:
            if action.action_type == 'deduction' and action.payslip_id:
                raise UserError(self.env._("You cannot draft a disciplinary action already linked to a payslip"))
            action.state = 'draft'

    def action_view_payslip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Payslip'),
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'res_id': self.payslip_id.id,
            'target': 'current',
        }

    def _calculate_deduction_amount(self):
        self.ensure_one()
        employee = self.employee_id
        amount_based_on = self.amount_based_on
        final_amount = 0.0
        base_salary = 0.0

        if self.action_type != 'deduction':
            return 0.0

        if amount_based_on == 'custom_amount':
            final_amount = self.amount
        elif amount_based_on in ['daily_wage_percentage', 'monthly_wage_percentage']:
            if self.amount_base_basic:
                base_salary += employee.version_id.wage
            if self.amount_base_housing:
                base_salary += employee.version_id.l10n_sa_housing_allowance
            if self.amount_base_transportation:
                base_salary += employee.version_id.l10n_sa_transportation_allowance
            if self.amount_base_other:
                base_salary += employee.version_id.l10n_sa_other_allowances

            if amount_based_on == 'monthly_wage_percentage':
                final_amount = base_salary * self.percentage
            else:
                days = 30.0
                if self.daily_wage_based_on == 'calendar_days':
                    days = float(monthrange(self.date.year, self.date.month)[1])
                elif self.daily_wage_based_on == 'working_days':
                    res_cal = employee.version_id.resource_calendar_id
                    month_start = self.date.replace(day=1)
                    next_month = self.date.replace(day=1, month=self.date.month + 1)
                    start_dt = fields.Datetime.to_datetime(month_start)
                    end_dt = fields.Datetime.to_datetime(next_month) - relativedelta(seconds=1)
                    days = float(res_cal.get_work_duration_data(start_dt, end_dt)['days'])

                final_amount = (base_salary / days) * self.percentage
        return final_amount

    @api.ondelete(at_uninstall=False)
    def _unlink_except_action_approved(self):
        if any(action.state == 'approved' for action in self):
            raise UserError(self.env._("You cannot delete a disciplinary action that has already been approved"))
