from odoo import http
from odoo.http import request


class AccountLoanExtractController(http.Controller):
    @http.route('/account_loan_extract/request_done/<string:extract_document_uuid>', type='http', auth='public', csrf=False)
    def request_done(self, extract_document_uuid):
        """ This webhook is called when the extraction server is done processing a request."""
        loans_to_update = request.env['account.loan'].sudo().search([
            ('extract_document_uuid', '=', extract_document_uuid),
            ('extract_state', 'in', ['waiting_extraction', 'extract_not_ready']),
            ('is_in_extractable_state', '=', True)])
        for loan in loans_to_update:
            loan._check_ocr_status()
        return 'OK'
