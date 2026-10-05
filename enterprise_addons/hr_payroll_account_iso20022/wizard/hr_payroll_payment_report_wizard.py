from uuid import uuid4

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        selection.extend([
            ('sepa', 'SEPA'),
            ('iso20022_ch', 'Swiss ISO20022'),
        ])
        return selection

    def _get_default_export_format(self):
        super()._get_default_export_format()
        return 'sepa'

    journal_id = fields.Many2one(
        string='Bank Journal', comodel_name='account.journal', required=True,
        default=lambda self: self.env['account.journal'].search([('type', '=', 'bank')], limit=1))
    sepa_priority = fields.Selection(
        selection=[('std', 'Standard'), ('high', 'High'), ('sct', 'SCT (Instant Credit Transfer)')],
        default='std',
        string='Priority',
        help='Instant payments will be directly proceeded by the bank but implies additional fees.'
    )
    payment_method_line_id = fields.Many2one(
        comodel_name='account.payment.method.line',
        string='Payment Method Line',
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'outbound'), ('payment_method_id.code', 'in', ['sepa_ct', 'iso20022_ch'])]",
        help='The payment method to use for this payment report. It will determine the XML format to use.',
    )

    def _create_sepa_binary(self):
        payslips_to_work_on = self.payslip_ids
        if self.include_unpaid:
            payslips_to_work_on = self.unpaid_payslips
        # Map the necessary data
        grouped_payments = {}
        for slip in payslips_to_work_on:
            if self.payment_method_line_id.sepa_pain_version == 'pain.001.001.09':
                if not slip.iso20022_uetr:
                    iso20022_uetr = slip.iso20022_uetr = str(uuid4())
                else:
                    iso20022_uetr = slip.iso20022_uetr
            else:
                iso20022_uetr = False

            allocations = slip._compute_salary_allocations()
            for ba in slip.employee_id.bank_account_ids | slip.salary_attachment_ids.beneficiary_bank_account_id:
                amount = allocations.get(str(ba.id))
                if not amount:
                    continue
                if ba.id in grouped_payments:
                    grouped_payments[ba.id]['amount'] += amount
                    if slip.employee_id.work_contact_id.id == ba.partner_id.id:
                        grouped_payments[ba.id]['id'] = slip.id
                        grouped_payments[ba.id]['name'] = f'{slip.id}-{ba.id}'
                        grouped_payments[ba.id]['memo'] = slip._get_iso20022_communication(ba)
                else:
                    grouped_payments[ba.id] = {
                        'id': slip.id,
                        'name': f'{slip.id}-{ba.id}',
                        'payment_date': self.effective_date or fields.Date.context_today(self),
                        'amount': amount,
                        'journal_id': self.journal_id.id,
                        'currency_id': self.journal_id.currency_id.id,
                        'payment_type': 'outbound',
                        'memo': slip._get_iso20022_communication(ba),
                        'partner_id': ba.partner_id.id,
                        'partner_bank_id': ba.id,
                        'iso20022_charge_bearer': self.journal_id.iso20022_charge_bearer,
                        # The "High" priority level is a payment attribute that we should specify for salary payments :
                        # https://www.febelfin.be/sites/default/files/2019-04/standard-credit_transfer-xml-v32-en_0.pdf
                        # section 2.6
                        'iso20022_priority': 'HIGH' if self.sepa_priority != 'std' else 'NORM',
                        'sepa_priority': self.sepa_priority,
                    }
                if iso20022_uetr:
                    grouped_payments[ba.id]['iso20022_uetr'] = iso20022_uetr

        payments_data = []
        for payment in grouped_payments.values():
            if payment['amount'] > 0:
                payments_data.append(payment)

        # Generate XML File
        return self.journal_id.sudo().with_context(
            sepa_payroll_sala=True,
            l10n_be_hr_payroll_sepa_salary_payment=self.journal_id.company_id.account_fiscal_country_id.code == "BE"
        ).create_iso20022_credit_transfer(payments=payments_data, payment_method_line=self.payment_method_line_id, batch_booking=True)

    def _perform_checks(self):
        super()._perform_checks()
        if self.export_format in ['sepa', 'iso20022_ch']:
            if self.effective_date < fields.Date.today():
                raise ValidationError(_("The payment date cannot be in the past."))
            employees = self.payslip_ids.employee_id.filtered(lambda e: not e.work_contact_id)
            if employees:
                raise UserError(_("Some employees (%s) don't have a work contact.", employees.mapped('name')))
            employees = self.payslip_ids.employee_id.filtered(lambda e: e.work_contact_id and not e.work_contact_id.name)
            if employees:
                raise UserError(_(
                    "Some employees (%s) don't have a valid name on the work contact.",
                    employees.mapped('name')))
            if self.journal_id.bank_account_id.account_type != 'iban':
                raise UserError(_(
                    "The journal '%s' requires a proper IBAN account to pay via SEPA. "
                    "Please configure it first.",
                    self.journal_id.name))
            if not self.payment_method_line_id:
                raise UserError(self.env._("No payment method found. Check the outgoing payment methods linked to the journal '%s'.", self.journal_id.name))

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format in ['sepa', 'iso20022_ch']:
            payment_report = self._create_sepa_binary()
            self._write_file(payment_report, '.xml')
