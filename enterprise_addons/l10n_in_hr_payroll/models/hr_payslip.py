# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime, time
from dateutil.relativedelta import relativedelta

from odoo import api, models, _
from odoo.tools import format_date, date_utils


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_l10n_in_employee_working_time(self, return_hours=False):
        self.ensure_one()
        slip_date_time = datetime.combine(self.date_from, time(12, 0, 0))
        employee_work_data = self.employee_id.resource_calendar_id.get_work_duration_data(
            date_utils.start_of(slip_date_time, 'month'),
            date_utils.end_of(slip_date_time, 'month'))
        if return_hours:
            return employee_work_data['hours']
        return employee_work_data['days']

    # No longer used. To be removed in master.
    def _get_l10n_in_company_working_time(self, return_hours=False):
        self.ensure_one()
        slip_date_time = datetime.combine(self.date_from, time(12, 0, 0))
        company_work_data = self.company_id.resource_calendar_id.get_work_duration_data(
            date_utils.start_of(slip_date_time, 'month'),
            date_utils.end_of(slip_date_time, 'month'))
        if return_hours:
            return company_work_data['hours']
        return company_work_data['days']

    @api.depends('employee_id', 'struct_id', 'date_from', 'is_refund_payslip', 'is_correction_payslip', 'origin_payslip_id.name')
    @api.depends_context('lang')
    def _compute_name(self):
        super()._compute_name()
        for slip in self.filtered(lambda s: s.country_code == 'IN'):
            if not slip.date_from:
                slip.name = False
            else:
                payslip_name = slip.title or slip.struct_id.payslip_name or _('Salary Slip')
                date = format_date(self.env, slip.date_from, date_format="MMMM y")
                full_name = '%(payslip_name)s - %(dates)s' % {
                    'payslip_name': payslip_name,
                    'dates': date
                }
                if slip.is_refund_payslip:
                    origin_name = slip.origin_payslip_id.name if slip.origin_payslip_id else full_name
                    full_name = _("Refund: %(payslip)s", payslip=origin_name)
                elif slip.is_correction_payslip:
                    origin_name = slip.origin_payslip_id.name if slip.origin_payslip_id else full_name
                    full_name = _("Correction: %(payslip)s", payslip=origin_name)
                slip.name = full_name

    def _l10n_in_prepare_challan_line_values_from_payslips(self):
        if not (payslips := self.filtered(lambda slip: slip.state == 'paid' and not slip.is_refund_payslip)):
            return {}

        line_values_by_code = payslips._get_line_values(['TDS'], ['total'])
        tds_paid_by_payslip = defaultdict(float)
        for payslip in payslips:
            total_tds_paid = max(-line_values_by_code.get('TDS', {}).get(payslip.id, {}).get('total', 0.0), 0.0)
            tds_paid_by_payslip[payslip] = round(total_tds_paid, 2)
        return tds_paid_by_payslip

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_in_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_payroll_structure_type_data.xml',
                'data/hr_rule_parameters_data.xml',
                'data/res_partner_data.xml',
                'data/salary_rules/hr_salary_rule_regular_pay_data.xml',
                'data/salary_rules/hr_salary_rule_stipend_data.xml',
            ])]

    def _get_base_local_dict(self):
        return {**super()._get_base_local_dict(), '_': lambda *a, **kw: self.env._(*a, **kw)}  # pylint: disable=E8502

    def _l10n_in_is_tds_deduction_month(self):
        """Check whether TDS should be deducted for this payslip based on the schedule."""
        self.ensure_one()
        schedule = self.version_id.l10n_in_tds_deduction_cycle
        if schedule == 'monthly':
            return True
        return self.date_to.month in self.employee_id._l10n_in_get_tds_deduction_months(schedule)

    def _get_employee_timeoff_data(self):
        return self.env['hr.work.entry.type'].with_company(self.company_id).with_context(employee_id=self.employee_id.id).get_allocation_data_request()

    def get_month(self):
        from_date = min(self.mapped('date_from'))
        to_date = max(self.mapped('date_to'))
        return {
            'from_name': format_date(self.env, from_date, date_format='long'),
            'to_name': format_date(self.env, to_date, date_format='long')
        }

    def action_payslip_payment_report(self, export_format='advice'):
        action = super().action_payslip_payment_report()
        if self.company_id.country_code != 'IN':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action

    def _l10n_in_get_due_period(self, cycle):
        """
        Utility function for getting the due period for lwf and professional tax deductions
        """
        self.ensure_one()
        due_months = {
            'monthly': set(range(1, 13)),
            'quarterly': {3, 6, 9, 12},
            'half_yearly': {6, 12},
            'yearly': {12},
        }.get(cycle)
        if not due_months:
            return False
        due_date = self.date_to.replace(day=1)
        months_checked = 0
        while months_checked < 12:
            if due_date.month in due_months:
                break
            due_date -= relativedelta(months=1)
            months_checked += 1
        else:
            return False
        join_date = self.version_id.contract_date_start or self.date_from
        if due_date < join_date.replace(day=1):
            return False
        return due_date, 12 // len(due_months)

    def _l10n_in_apply_lwf_or_professional_tax_deductions(self, rule_code):
        # Current rule_codes: LWFE, LWF, PT, PTD (First two for LWF, Last two for Professional Tax)
        due_period = self._l10n_in_get_lwf_due_period() if rule_code in ('LWFE', 'LWF') else self._l10n_in_get_professional_tax_due_period()
        if not due_period:
            return False
        due_date, step = due_period
        return not self.env['hr.payslip.line'].search_count(
            [
                ('slip_id', '!=', self.id),
                ('slip_id.employee_id', '=', self.employee_id.id),
                ('slip_id.company_id', '=', self.company_id.id),
                ('slip_id.state', '!=', 'cancel'),
                ('slip_id.date_to', '>=', due_date),
                ('slip_id.date_from', '<', due_date + relativedelta(months=step)),
                ('code', '=', rule_code),
                ('total', '!=', 0),
            ],
            limit=1,
        )

    def _l10n_in_get_professional_tax_due_period(self):
        self.ensure_one()
        cycle = self.version_id.l10n_in_professional_tax_deduction_cycle
        return self._l10n_in_get_due_period(cycle)

    def _l10n_in_apply_professional_tax_deduction(self, rule_code):
        self.ensure_one()
        if not (rule_code in ('PT', 'PTD') and self.country_code == 'IN' and self.date_from and self.date_to):
            return False
        return self._l10n_in_apply_lwf_or_professional_tax_deductions(rule_code)

    def _l10n_in_get_lwf_due_period(self):
        self.ensure_one()
        cycle = self.version_id.l10n_in_lwf_deduction_cycle
        return self._l10n_in_get_due_period(cycle)

    def _l10n_in_apply_lwf(self, rule_code):
        self.ensure_one()
        if not (rule_code in ('LWFE', 'LWF') and self.country_code == 'IN' and self.date_from and self.date_to):
            return False
        return self._l10n_in_apply_lwf_or_professional_tax_deductions(rule_code)

    def _l10n_in_taxable_gross_total(self, grouped_payslips):
        """Return taxable gross and TDS totals for grouped payslips.

        The result is a map of employee id to ``(gross, tds)``.
        """
        result = {}
        all_payslip_ids = []

        for _employee, payslips in grouped_payslips:
            all_payslip_ids.extend(payslips.ids)
        if not all_payslip_ids:
            return result

        gross_by_payslip = {}
        tds_by_payslip = {}
        for payslip, code, total in self.env['hr.payslip.line'].sudo()._read_group(
            domain=[
                ('slip_id', 'in', all_payslip_ids),
                '|',
                    ('code', 'in', ['GROSS', 'TDS']),
                    ('salary_rule_id.category_ids', 'any', [
                        ('code', '=', 'NONTAX'),
                    ]),
            ],
            groupby=['slip_id', 'code'],
            aggregates=['total:sum'],
        ):
            amount = total or 0.0
            payslip_id = payslip.id
            if code == 'GROSS':
                gross_by_payslip[payslip_id] = gross_by_payslip.get(payslip_id, 0.0) + amount
            elif code == 'TDS':
                tds_by_payslip[payslip_id] = tds_by_payslip.get(payslip_id, 0.0) + max(-amount, 0.0)
            else:
                gross_by_payslip[payslip_id] = gross_by_payslip.get(payslip_id, 0.0) + amount

        for employee, payslips in grouped_payslips:
            payslip_ids = payslips.ids
            gross = sum(gross_by_payslip.get(payslip_id, 0.0) for payslip_id in payslip_ids)
            tds = sum(tds_by_payslip.get(payslip_id, 0.0) for payslip_id in payslip_ids)
            result[employee.id] = (gross, tds)

        return result
