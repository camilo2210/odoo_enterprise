# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import format_date


class HrPayrollSalaryIncrease(models.TransientModel):
    _name = 'hr.payroll.salary.increase'
    _description = 'Index contracts'

    employee_ids = fields.Many2many('hr.employee', string="Employees", required=True)
    increase_date = fields.Date('Date of Salary Increase', required=True)
    increase_rate = fields.Float("Increase Rate", digits="Payroll Rate",
                                 help="A salary of 5000$ indexed by 10% will give 5500$ as a result")
    applied_on = fields.Selection([
        ('full', 'Full Wage'),
        ('capped', 'Capped Wage')
    ], string="Applies on", default="full", required=True,
        help="A salary of 5000$ capped to 4000$ indexed by 10% will give 5400$ as a result")
    capped_wage = fields.Float("Capped Wage Amount")
    extra_amount = fields.Float("Extra Amount")
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        readonly=True, required=True
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    has_affected_versions = fields.Boolean(string="Affected Versions", compute="_compute_has_affected_versions")
    state = fields.Selection([
        ('increase', 'Salary Increase'),
        ('correction', 'Payslip Correction'),
    ], default='increase', required=True)
    affected_payslip_ids = fields.Many2many('hr.payslip', string="Affected Payslips")
    affected_payslip_count = fields.Integer(compute='_compute_affected_payslip_count')

    @api.depends('affected_payslip_ids')
    def _compute_affected_payslip_count(self):
        for wizard in self:
            wizard.affected_payslip_count = len(wizard.affected_payslip_ids)

    @api.depends("employee_ids", "increase_date")
    def _compute_has_affected_versions(self):
        for wizard in self:
            wizard.has_affected_versions = any(
                self._get_affected_version_ids(employee)[1] for employee in self.employee_ids
            ) if wizard.increase_date else False

    def _get_affected_version_ids(self, employee):
        self.ensure_one()
        versions_before = employee.version_ids.filtered_domain([('date_version', '<=', self.increase_date)])
        if not versions_before:
            return None, None
        increase_base_version = versions_before[-1]
        # keep all versions related to the same contract
        return increase_base_version, employee.version_ids.filtered(
            lambda v: v.date_version >= increase_base_version.date_version and v.contract_date_start == increase_base_version.contract_date_start
                and v.contract_date_end == increase_base_version.contract_date_end
        ) - increase_base_version

    def _get_increased_wage(self, current_wage):
        capped_wage = min(current_wage, self.capped_wage) if self.applied_on == 'capped' and self.capped_wage else current_wage
        return current_wage + self.extra_amount + (capped_wage * self.increase_rate)

    def _build_increase_message(self, future_affected_versions):
        currency_amount = self.currency_id.format(self.extra_amount)
        message_body = self.env._(
            'Wage increased by %(percentage).2f%%%(capped)s%(extra)s starting from %(increase_date)s on %(date)s.',
            percentage=self.increase_rate * 100,
            capped=self.env._(' (applied to capped wage of %(capped_wage)s)', capped_wage=self.capped_wage) if self.capped_wage else '',
            extra=self.env._(' and a fixed extra amount of %(extra_amount)s (FTE)', extra_amount=currency_amount) if self.extra_amount else '',
            increase_date=format_date(self.env, self.increase_date),
            date=format_date(self.env, fields.Date.today()),
        )
        if future_affected_versions:
            message_body += Markup("<br/><b>%s</b><ul>") % self.env._("Impacted Employee Records:")
            for v in future_affected_versions:
                message_body += Markup("<li><b>%s</b></li>") % v.display_name
            message_body += Markup("</ul>")
        return message_body

    def action_confirm(self):
        self.ensure_one()

        self._indexation_issues_check()

        version_map = {e: self._get_affected_version_ids(e) for e in self.employee_ids}
        employees_without_version = self.employee_ids.filtered(lambda e: version_map[e][0] is None)
        if employees_without_version:
            raise ValidationError(
                self.env._(
                    'Cannot apply the salary increase because no employee version exists for the selected increase date for:\n- %(employees)s',
                    employees='\n- '.join(employees_without_version.mapped('name')),
                ),
            )

        for employee in self.employee_ids:
            base_version, future_versions = version_map[employee]
            self._index_wage(employee, base_version)
            self._index_future_versions(future_versions)

            message_body = self._generate_indexation_message(future_versions)
            employee.with_context(mail_post_autofollow_author_skip=True).message_post(
                body=message_body,
                message_type="comment",
                subtype_xmlid="mail.mt_note"
            )

        affected_payslips = self.env['hr.payslip'].search(Domain.AND([
            Domain('employee_id', 'in', self.employee_ids.ids),
            Domain('date_from', '>=', self.increase_date),
            Domain('state', 'in', ['validated', 'paid']),
            Domain('is_refund_payslip', '=', False),
            Domain('is_refunded', '=', False),
        ]))

        if affected_payslips:
            self.affected_payslip_ids = affected_payslips
            if len(self.employee_ids) == 1:
                return self._open_correction_wizard()
            self.state = 'correction'
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _indexation_issues_check(self):
        if self.increase_rate < 0:
            raise UserError(self.env._('Cannot increase a wage with a negative percentage.'))
        if self.extra_amount < 0:
            raise UserError(self.env._('Cannot increase a wage with a negative amount.'))
        if not self.increase_rate and not self.extra_amount:
            raise UserError(self.env._('You should at least set an increase rate or an extra amount.'))

    def _index_wage(self, employee, base_version):
        wage_field = base_version._get_contract_wage_field()

        new_wage = self._get_increased_wage(base_version[wage_field])
        # do not create version if a version already exists for this exact date.
        if base_version.date_version != self.increase_date:
            employee.create_version({'date_version': self.increase_date, wage_field: new_wage})
        else:
            base_version[wage_field] = new_wage

    def _index_future_versions(self, future_versions):
        if not future_versions:
            return
        wage_field = future_versions._get_contract_wage_field()
        for version in future_versions:
            version[wage_field] = self._get_increased_wage(version[wage_field])

    def _generate_indexation_message(self, future_affected_versions):
        currency_amount = self.currency_id.format(self.extra_amount)
        message_body = self.env._(
            'Wage manually increased by %(percentage).2f%%%(capped)s%(extra)s starting from %(increase_date)s on %(date)s.',
            percentage=self.increase_rate * 100,
            capped=self.env._(' (applied to capped wage of %(capped_wage)s)', capped_wage=self.capped_wage) if self.capped_wage else '',
            extra=self.env._(' and a fixed extra amount of %(extra_amount)s (FTE)', extra_amount=currency_amount) if self.extra_amount else '',
            increase_date=format_date(self.env, self.increase_date),
            date=format_date(self.env, fields.Date.today()),
        )
        if future_affected_versions:
            message_body += Markup("<br/><b>%s</b><ul>") % self.env._("Impacted Employee Records:")
            for v in future_affected_versions:
                message_body += Markup("<li><b>%s</b></li>") % v.display_name
            message_body += Markup("</ul>")
        return message_body

    def _open_correction_wizard(self):
        correction_wizard = self.env['hr.payslip.correction.wizard'].create({
            'employee_ids': [Command.set([self.affected_payslip_ids.employee_id.id])],
            'payslip_ids': [Command.set([self.affected_payslip_ids[0].id])],
            'correction_choice': 'multi',
        })
        view = self.env.ref('hr_payroll.hr_payslip_correction_wizard_form_salary_increase', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.correction.wizard',
            'res_id': correction_wizard.id,
            'views': [(view.id if view else False, 'form')],
            'target': 'new',
        }

    def action_correct_payslips(self):
        self.ensure_one()
        if len(self.affected_payslip_ids.employee_id) == 1:
            return self._open_correction_wizard()
        return self.affected_payslip_ids._get_payslips_action()
