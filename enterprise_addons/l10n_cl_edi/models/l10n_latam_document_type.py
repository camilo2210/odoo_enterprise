from odoo import api, fields, models
from odoo.exceptions import UserError


class L10n_LatamDocumentType(models.Model):
    _inherit = 'l10n_latam.document.type'

    l10n_cl_dte_caf_ids = fields.One2many('l10n_cl.dte.caf', 'l10n_latam_document_type_id', string='DTE Caf')
    l10n_cl_show_caf_button = fields.Boolean(compute='_l10n_cl_show_caf_button')

    @api.depends_context('company')
    @api.depends('l10n_cl_dte_caf_ids', 'country_id', 'internal_type')
    def _l10n_cl_show_caf_button(self):
        company = self.env.company
        caf_owners = company | company._l10n_cl_get_root_company()
        for r in self:
            r.l10n_cl_show_caf_button = r.internal_type and \
                company.l10n_cl_dte_service_provider == 'SIIDEMO' and r.country_id.code == 'CL' and not \
                r.l10n_cl_dte_caf_ids.filtered(lambda c: c.company_id in caf_owners)

    def _is_doc_type_ticket(self):
        return self.code in ['35', '38', '39', '41', '70', '71']

    def _is_doc_type_voucher(self):
        return self.code in ['35', '39', '41', '906', '45', '70', '71']

    def _is_doc_type_exempt(self):
        return self.code in ['34', '110', '111', '112']

    def _is_doc_type_acceptance(self):
        """
        Check if the document type can be accepted or claimed
        """
        return self.code in ['33', '34', '56', '61', '43']

    def _get_caf_file(self, company_id, folio):
        cafs = self.env['res.company'].browse(company_id)._l10n_cl_get_cafs(self)
        if caf := cafs.filtered(lambda caf: caf.status == 'in_use' and caf.start_nb <= folio <= caf.final_nb)[:1]:
            return caf._decode_caf()
        if cafs:
            raise UserError(self.env._(
                'Folio %(folio)s is in none of the CAF ranges %(company)s still has for %(document_type)s. '
                'Please upload its next CAF file or ask for a new one at www.sii.cl website.',
                folio=folio, company=cafs.company_id.display_name, document_type=self.name))
        raise UserError(self.env._(
            'There are no CAFs available for folio %(folio)s in the sequence of %(document_type)s. '
            'Please upload a CAF file or ask for a new one at www.sii.cl website.',
            folio=folio, document_type=self.name))

    def create_demo_caf_file(self):
        self.env.company._create_demo_caf_files(enabled_dte_documents=self)
