from odoo import api, models, _, Command

OCR_VERSION = 100


class AccountLoan(models.Model):
    _name = 'account.loan'
    _inherit = ['extract.mixin.with.words', 'account.loan']

    @api.depends('line_ids')
    def _compute_is_in_extractable_state(self):
        self.is_in_extractable_state = not self.line_ids

    def _get_ocr_option_can_extract(self):
        ocr_option = self.env.company.extract_loan_digitalization_mode
        return ocr_option and ocr_option != 'no_send'

    def _get_ocr_module_name(self):
        return 'account_loan_extract'

    @api.model
    def _get_ocr_api_version(self):
        return OCR_VERSION

    @api.model
    def _get_api_route(self):
        return 'api/extract/loan/2'

    def _fill_document_with_results(self, ocr_results):
        self.ensure_one()

        amount_loan_ocr = self._get_ocr_selected_value(ocr_results, 'amount_loan')
        amount_interests_ocr = self._get_ocr_selected_value(ocr_results, 'amount_interests')
        duration_months_ocr = self._get_ocr_selected_value(ocr_results, 'duration_months')
        date_ocr = self._get_ocr_selected_value(ocr_results, 'date')
        lines_ocr = ocr_results.get('loan_amortization_lines', [])

        if not self.amount_borrowed and amount_loan_ocr:
            self.amount_borrowed = amount_loan_ocr

        if not self.interest and amount_interests_ocr:
            self.interest = amount_interests_ocr

        if not self.duration and duration_months_ocr:
            self.duration = duration_months_ocr

        if not self.date and date_ocr:
            self.date = date_ocr

        if not self.line_ids and lines_ocr:
            self.line_ids = [Command.create({
                'date': line['date'],
                'principal': line['principal'],
                'interest': line['interest'],
                'outstanding_balance': line['outstanding_balance'],
            }) for line in lines_ocr]

    def _message_set_main_attachment_id(self, attachments, force=False, filter_xml=True):
        res = super()._message_set_main_attachment_id(attachments, force=force, filter_xml=filter_xml)
        self._autosend_for_digitization()
        return res

    def _autosend_for_digitization(self):
        if self.env.company.extract_loan_digitalization_mode == 'auto_send':
            self.filtered('extract_can_show_send_button')._send_batch_for_digitization()

    def action_upload_amortization_schedule(self, attachment_id):
        """Called when uploading an amortization schedule file"""
        attachment = self.env['ir.attachment'].browse(attachment_id)

        if attachment.mimetype not in ('application/pdf', 'image/jpeg', 'image/png'):
            return super().action_upload_amortization_schedule(attachment_id)

        loan = self.create({
            'name': attachment.name,
        })
        attachment.write({
            'res_model': loan._name,
            'res_id': loan.id,
        })
        loan.message_post(body=_('Uploaded file'), attachment_ids=[attachment.id])

        action = {
            'type': 'ir.actions.act_window',
            'name': _("Loans"),
            'res_model': 'account.loan',
            'res_id': loan.id,
            'views': [(False, 'form')],
            'target': 'self',
        }
        return action
