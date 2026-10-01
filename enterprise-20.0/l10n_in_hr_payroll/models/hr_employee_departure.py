# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrEmployeeDeparture(models.Model):
    _inherit = 'hr.employee.departure'

    l10n_in_notice_period_start = fields.Date(
        string='Start of Notice Period',
        compute='_compute_l10n_in_notice_period_start',
        store=True,
        readonly=False,
    )
    l10n_in_notice_duration = fields.Char(
        string='Notice Duration',
        compute='_compute_l10n_in_notice_duration',
    )

    @api.depends('dismissal_date')
    def _compute_l10n_in_notice_period_start(self):
        for departure in self:
            departure.l10n_in_notice_period_start = departure.dismissal_date

    @api.depends('l10n_in_notice_period_start')
    def _compute_departure_date(self):
        super()._compute_departure_date()
        for departure in self:
            if departure.country_code == 'IN' and departure.l10n_in_notice_period_start:
                departure.departure_date = departure.l10n_in_notice_period_start + relativedelta(months=1)

    @api.depends('l10n_in_notice_period_start', 'departure_date')
    def _compute_l10n_in_notice_duration(self):
        for departure in self:
            if departure.l10n_in_notice_period_start and departure.departure_date:
                delta = relativedelta(departure.departure_date, departure.l10n_in_notice_period_start)
                months = delta.months + (delta.years * 12)
                days = delta.days
                parts = []
                if months:
                    parts.append(self.env._('%(count)s months', count=months))
                if days:
                    parts.append(self.env._('%(count)s days', count=days))
                departure.l10n_in_notice_duration = ' '.join(parts) or self.env._('0 days')
            else:
                departure.l10n_in_notice_duration = ''

    @api.constrains('departure_date')
    def _l10n_in_check_departure_date_validity(self):
        in_departures = self.filtered(lambda d: d.country_code == 'IN')
        if in_departures:
            in_departures._check_departure_validity()

    def action_schedule(self):
        self._l10n_in_send_notice_period_email()
        return super().action_schedule()

    def action_register(self):
        res = super().action_register()
        in_departures = self.filtered(lambda d: d.country_code == 'IN')
        fnf_payslips = in_departures._l10n_in_generate_fnf_payslips()
        if fnf_payslips:
            return {
                'name': self.env._('FNF Payslips'),
                'view_mode': 'list',
                'res_model': 'hr.payslip',
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', fnf_payslips.ids)],
                'views': [[False, 'list'], [False, 'form']],
            }
        return res

    def _l10n_in_generate_fnf_payslips(self):
        vals_list = [{
            'title': self.env._('FNF Payslip'),
            'employee_id': departure.employee_id.id,
            'date_from': departure.departure_date + relativedelta(day=1),
        } for departure in self.filtered('departure_date')]
        if not vals_list:
            return self.env['hr.payslip']
        fnf_payslips = self.env['hr.payslip'].create(vals_list)
        fnf_payslips.compute_sheet()
        return fnf_payslips

    def _l10n_in_send_notice_period_email(self):
        to_notify = self.filtered(
            lambda d: d.country_code == 'IN' and d.employee_id.work_email
        )
        if not to_notify:
            return
        template = self.env.ref('l10n_in_hr_payroll.l10n_in_mail_template_notice_period', raise_if_not_found=False)
        if template:
            template.send_mail_batch(to_notify.ids)
