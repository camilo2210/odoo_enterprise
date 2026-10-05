import csv

from io import StringIO

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import BinaryBytes
from odoo.tools.misc import format_amount, format_date


class HrPayrollPaymentReportWizard(models.TransientModel):
    _name = 'hr.payroll.payment.report.wizard'

    _description = 'HR Payroll Payment Report Wizard'

    def _get_export_format_selection(self):
        return [
            ("manual", "Manually"),
            ("csv", "CSV"),
        ]

    def _get_default_export_format(self):
        return 'manual'

    payslip_run_id = fields.Many2one('hr.payslip.run', check_company=True)
    payslip_ids = fields.Many2many('hr.payslip', required=True, check_company=True)
    unpaid_payslips = fields.Many2many(
        string='Payslips to Include',
        comodel_name='hr.payslip',
        relation='wizard_unpaid_payslip_rel',
    )
    allowed_unpaid_payslip_ids = fields.Many2many(
        string='Unpaid slips',
        comodel_name='hr.payslip',
        relation='allowed_unpaid_payslip_rel',
    )
    export_format = fields.Selection(selection='_get_export_format_selection', string='Mode', required=True, default=_get_default_export_format)
    company_id = fields.Many2one('res.company', compute="_compute_company_id")
    effective_date = fields.Date(
        string='Payment Date',
        help='Payment Entry Date: the banking day on which you intend the payslip batch to be settled.',
        default=fields.Date.context_today, required=True)
    include_unpaid = fields.Boolean(
        string='Include Unpaid',
        help='This option is to allow for including other payslips in the same payment.'
    )
    unpaid_payslips_description = fields.Char(compute="_compute_unpaid_payslips_description")
    payment_report = fields.Binary(string='Payment Report', readonly=True)
    payment_report_filename = fields.Char(string='Payment Report Filename', readonly=True)

    @api.depends('payslip_ids')
    def _compute_company_id(self):
        self.company_id = self.payslip_ids[0].company_id

    def _create_csv_binary(self):
        today = fields.Date.context_today(self)
        output = StringIO()
        report_data = csv.writer(output)
        report_data.writerow([_('Sequence'), _('Payment Date'), _('Report Date'), _('Payment Period'), _('Employee name'), _('Bank account'), _('BIC'), _('Amount to pay')])
        grouped_payments = {}
        payslips_to_work_on = self.payslip_ids
        if self.include_unpaid:
            payslips_to_work_on = self.unpaid_payslips

        for slip in payslips_to_work_on:
            allocations = slip._compute_salary_allocations()
            for ba in slip.employee_id.bank_account_ids | slip.salary_attachment_ids.beneficiary_bank_account_id:
                amount = allocations.get(str(ba.id))
                legal_name = ba.partner_id.name
                if not amount:
                    continue
                if ba.id in grouped_payments:
                    grouped_payments[ba.id]['amount'] += amount
                    grouped_payments[ba.id]['payment_period_start'] = min(grouped_payments[ba.id]['payment_period_start'], slip.date_from)
                    grouped_payments[ba.id]['payment_period_end'] = max(grouped_payments[ba.id]['payment_period_end'], slip.date_to)

                else:
                    grouped_payments[ba.id] = {
                        'payment_date': format_date(self.env, self.effective_date),
                        'report_date':  format_date(self.env, today),
                        'payment_period_start': slip.date_from,
                        'payment_period_end': slip.date_to,
                        'employee_name': legal_name,
                        'bank_account': ba.account_number,
                        'bank_bic': ba.bank_bic or '',
                        'currency': slip.currency_id,
                        'amount': amount,
                    }
        rows = []
        for index, data in enumerate(grouped_payments.values(), start=1):
            if data['amount'] > 0:
                rows.append((
                    str(index),
                    data['payment_date'],
                    data['report_date'],
                    format_date(self.env, data['payment_period_start']) + ' - ' + format_date(self.env, data['payment_period_end']),
                    data['employee_name'],
                    data['bank_account'],
                    data['bank_bic'],
                    format_amount(self.env, data['amount'], data['currency']),
                ))
        report_data.writerows(rows)
        return output.getvalue().encode()

    def _write_file(self, payment_report: bytes, extension, filename=''):
        today = fields.Date.context_today(self)
        self.payment_report = payment_report = BinaryBytes(payment_report)
        self.payment_report_filename = (filename or 'Payment Report') + extension

        if self.payslip_run_id:
            batch_filename = filename or _('Payment Report - %(batch_name)s', batch_name=self.payslip_run_id.name)
            self.payslip_run_id.write({
                'payment_report': payment_report,
                'payment_report_filename': batch_filename + extension,
                'payment_report_format': dict(self._fields['export_format']._description_selection(self.env))[self.export_format],
                'payment_report_date': today})

        for payslip in self.payslip_ids:
            payslip_filename = filename or _('Payment Report - %(dates)s - %(employee_name)s',
                                             dates=payslip._get_period_name({}),
                                             employee_name=payslip.employee_id.legal_name)
            payslip.write({
                'payment_report': payment_report,
                'payment_report_filename': payslip_filename + extension,
                'payment_report_date': today})

    def _perform_checks(self):
        """
        Extend this function and first call super()._perform_checks().
        Then make condition(s) for the format(s) you added and corresponding checks.
        The checks below are common to all payment reports.
        """
        if not self.payslip_ids:
            raise ValidationError(_('There should be at least one payslip to generate the file.'))
        payslips = self.payslip_ids.filtered(lambda p: p.state == "validated" and p.net_wage > 0)
        if not payslips:
            raise ValidationError(_('There is no valid payslip (validated and net wage > 0) to generate the file.'))

    def _write_payment_date(self):
        self.payslip_ids.write({
            'paid_date': self.effective_date
        })

    def generate_payment_report(self):
        """
        Extend this function and first call super().generate_payment_report().
        Then make condition(s) for the format(s) you added and corresponding methods.
        """
        self.ensure_one()
        if self.payslip_ids.filtered('error_count'):
            raise ValidationError(self.payslip_ids._get_error_message())
        self._perform_checks()
        if self.export_format == 'csv':
            payment_report = self._create_csv_binary()
            self._write_file(payment_report, '.csv')

    @api.depends('unpaid_payslips')
    def _compute_unpaid_payslips_description(self):
        for record in self:
            record.unpaid_payslips_description = self.env._("%s payslips selected", len(record.unpaid_payslips))

    def mark_as_paid(self):
        self.ensure_one()
        if self.export_format != 'manual' and not self.payment_report:
            self.generate_payment_report()
        self._write_payment_date()
        if self.include_unpaid:
            self.unpaid_payslips.action_payslip_paid()
        else:
            self.payslip_ids.action_payslip_paid()

    def download_report(self):
        self.ensure_one()
        if self.export_format == 'manual':
            return None
        self.generate_payment_report()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/payment_report/%s?download=true' % (self._name, self.id, self.payment_report_filename),
            'target': 'download',
        }
