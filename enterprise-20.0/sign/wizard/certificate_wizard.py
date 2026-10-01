# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class CertificateWizard(models.TransientModel):
    _name = "certificate.wizard"
    _description = "Certificate Creation Wizard"

    certificate_data = fields.Binary("Certificate File", required=True)
    certificate_filename = fields.Char("Filename")
    certificate_name = fields.Char(
        "Certificate Name",
        compute="_compute_certificate_name",
        store=True,
        readonly=False,
        required=True,
    )
    pkcs12_password = fields.Char(string='Certificate Password', help='Password to decrypt the PKS file.', required=True)

    @api.depends("certificate_data")
    def _compute_certificate_name(self):
        for wizard in self:
            if wizard.certificate_filename:
                wizard.certificate_name = wizard.certificate_filename
            else:
                wizard.certificate_name = ""

    def action_create_certificate(self):
        """ Create a new signing certificate, link it to the current company,
        and remove any existing signing certificate.
        """
        cert = self.env["certificate.certificate"].create({
            'name': self.certificate_name,
            'content': self.certificate_data,
            'pkcs12_password': self.pkcs12_password,
        })

        return {
            'type': 'ir.actions.act_window_close',
            'infos':  cert.id,
        }
