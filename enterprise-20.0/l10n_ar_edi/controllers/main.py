# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.http import Controller, request, route
from odoo.http.stream import content_disposition


class DownloadCertificateRequst(Controller):

    @route('/l10n_ar_edi/download_csr/<int:company_id>', type='http', auth="user")
    def download_csr(self, company_id, **kw):
        """ Download the certificate request file to upload in ARCA """
        content = self.env['certificate.certificate'].sudo()._l10n_ar_create_certificate_request(company_id)
        if not content:
            raise request.not_found()
        return request.make_response(content, headers=[
            ('Content-Type', 'text/plain'),
            ('Content-Disposition', content_disposition('request.csr'),
        )])
