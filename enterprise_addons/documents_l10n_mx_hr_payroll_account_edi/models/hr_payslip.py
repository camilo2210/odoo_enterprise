from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_mx_edi_cfdi_access_url = fields.Char(compute='_compute_cfdi_access_url')

    def _compute_cfdi_access_url(self):
        documents = self.env["documents.document"].search(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            order='res_id, id desc'
        )
        cfdi_url_per_payslip = dict()
        for document in documents:
            if document.name.endswith('MX-Nómina-12.xml') and document.res_id not in cfdi_url_per_payslip:
                cfdi_url_per_payslip[document.res_id] = document.access_url
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_access_url = cfdi_url_per_payslip.get(payslip.id)

    def _get_email_template(self):
        self.ensure_one()
        if self.country_code != 'MX':
            return super()._get_email_template()
        return self.env.ref(
            'documents_l10n_mx_hr_payroll_account_edi.l10n_mx_mail_template_new_payslip', raise_if_not_found=False
        )
