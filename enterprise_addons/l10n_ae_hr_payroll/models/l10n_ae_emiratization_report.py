# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import RedirectWarning
from odoo.tools.misc import format_date


class L10nAeEmiratizationReport(models.Model):
    _name = 'l10n_ae.emiratization.report'
    _description = 'Emiratization Compliance Report'

    name = fields.Char(string='Name', compute='_compute_name', store=True, readonly=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company.id,
        domain="[('partner_id.country_id.code', '=', 'AE')]")
    date_from = fields.Date(string='From', required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(string='To', required=True)
    line_ids = fields.One2many('l10n_ae.emiratization.report.line', 'report_id')
    new_employees_count = fields.Integer(compute='_compute_new_employees_count')
    growth_percentage = fields.Float(string='Growth %',
        help="Percentage growth in the number of Emirati employees for this period. Only employees whose MOHRE Skill Level is 5 or below are included in the calculation")
    emiratization_target_id = fields.Many2one('l10n_ae.emiratization.target')
    target_percentage = fields.Float(related="emiratization_target_id.target_percentage")

    _date_range = models.Constraint(
        'CHECK (date_from <= date_to)',
        "The start date must be anterior to the end date.",
    )

    @api.depends('line_ids')
    def _compute_new_employees_count(self):
        for report in self:
            report.new_employees_count = len(report.line_ids)

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from:
            self.date_to = self.date_from + relativedelta(months=6)

    @api.depends('date_from', 'date_to', 'company_id')
    def _compute_name(self):
        for report in self:
            report.name = self.env._(
                'Emiratization Compliance for %(company_name)s from %(date_from)s to %(date_to)s',
                company_name=report.company_id.name,
                date_from=format_date(self.env, report.date_from),
                date_to=format_date(self.env, report.date_to),
            )

    def _get_skilled_emirati_versions_on_date(self, date):
        groups = self.env['hr.version']._read_group(
            [
                ('company_id', '=', self.company_id.id),
                ('employee_id.country_id.code', '=', 'AE'),
                ('date_version', '<=', date),
                ('contract_date_start', '<=', date),
                '|',
                    ('contract_date_end', '=', False),
                    ('contract_date_end', '>', date),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset'],
        )
        result = self.env['hr.version']
        for _employee, versions in groups:
            effective = versions.sorted('date_version', reverse=True)[:1]
            if effective.job_id.l10n_ae_mohre_skill_level in ('1', '2', '3', '4', '5'):
                result |= effective
        return result

    def _get_applicable_emiratization_target(self, date):
        target = self.env['l10n_ae.emiratization.target'].search([
            ('effective_date', '<=', date),
        ], order='effective_date DESC', limit=1)
        if not target:
            action = self.env.ref('l10n_ae_hr_payroll.emiratization_target_action')
            raise RedirectWarning(
                self.env._('No Emiratization Target found for the selected period. Please create one first.'),
                action.id,
                self.env._('Go to Emiratization Targets'),
            )
        return target

    def action_populate(self):
        self.ensure_one()
        target = self._get_applicable_emiratization_target(self.date_to)

        versions_start = self._get_skilled_emirati_versions_on_date(self.date_from)
        versions_end = self._get_skilled_emirati_versions_on_date(self.date_to)

        count_start = len(versions_start.employee_id)
        count_end = len(versions_end.employee_id)

        start_employee_ids = versions_start.employee_id
        new_employee_versions = versions_end.filtered(lambda v: v.employee_id not in start_employee_ids)

        self.line_ids.sudo().unlink()

        self.write({
            "emiratization_target_id": target,
            "growth_percentage": (count_end - count_start) / count_start if count_start else count_end,
            "line_ids": [Command.clear()] + [Command.create({'version_id': version.id}) for version in new_employee_versions],
        })

        emirati_no_skill = self.env['hr.employee'].search([
            ('company_id', '=', self.company_id.id),
            ('country_id.code', '=', 'AE'),
            ('job_id.l10n_ae_mohre_skill_level', '=', False),
        ])
        if emirati_no_skill:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message':  self.env._("Some Emirati employees have no MOHRE Skill Level set on their job position."),
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                },
            }

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Emiratization Compliance Employees"),
            'res_model': 'l10n_ae.emiratization.report.line',
            'view_mode': 'list',
            'domain': [('id', 'in', self.line_ids.ids)],
            'context': {'search_default_group_by_job': True},
        }


class L10nAeEmiratizationReportLine(models.Model):
    _name = 'l10n_ae.emiratization.report.line'
    _description = 'Emiratization Compliance Report Line'

    report_id = fields.Many2one('l10n_ae.emiratization.report', required=True, index=True, ondelete='cascade')
    version_id = fields.Many2one('hr.version', string='Employee Record', required=True, readonly=True)
    employee_id = fields.Many2one(related='version_id.employee_id', required=True, readonly=True)
    department_id = fields.Many2one(related='version_id.department_id', string='Department')
    job_id = fields.Many2one(related='version_id.job_id', string='Job Title')
