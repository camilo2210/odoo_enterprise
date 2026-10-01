from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_cl_edi.tests.common import (
    TestL10nClEdiCommon,
    _check_with_xsd_patch,
    _is_valid_certificate,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
@patch('odoo.tools.xml_utils._check_with_xsd', _check_with_xsd_patch)
@patch('odoo.addons.certificate.models.certificate.CertificateCertificate._compute_is_valid', _is_valid_certificate)
class TestL10nClBranches(TestL10nClEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_company = cls.company_data['company']
        cls.branch_a, cls.branch_b = cls.env['res.company'].create([{
            'name': name,
            'parent_id': cls.parent_company.id,
            'country_id': cls.env.ref('base.cl').id,
            # a branch is created through the form, which copies these down from its parent
            'l10n_cl_dte_service_provider': 'SIITEST',
            'l10n_cl_dte_resolution_number': 0,
            'l10n_cl_dte_resolution_date': '2019-10-20',
            'l10n_cl_sii_regional_office': 'ur_SaC',
            'l10n_cl_company_activity_ids': [Command.set(cls.env.ref('l10n_cl_edi.eco_new_acti_620200').ids)],
        } for name in ('BMYA Sucursal A', 'BMYA Sucursal B')])
        (cls.branch_a | cls.branch_b).partner_id.write({
            'street': 'Apoquindo 6410',
            'city': 'Les Condes',
            'country_id': cls.env.ref('base.cl').id,
        })
        cls.env.user.company_ids = [Command.link(cls.branch_a.id), Command.link(cls.branch_b.id)]
        cls.partner_sii.company_id = False
        cls.tax_19 = cls.env['account.tax'].search([
            ('name', '=', '19% VAT'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.parent_company.id),
        ], limit=1)
        cls.branch_journals = {branch: cls.env['account.journal'].create({
            'name': 'Sale Journal %s' % branch.name,
            'type': 'sale',
            'code': code,
            'l10n_cl_point_of_sale_type': 'online',
            'l10n_latam_use_documents': True,
            'company_id': branch.id,
        }) for branch, code in ((cls.branch_a, 'INVSA'), (cls.branch_b, 'INVSB'))}
        # ranges of its own, disjoint, so branch B never draws on the ones the parent holds
        cls.caf_b_first, cls.caf_b_second = [cls.env['l10n_cl.dte.caf'].sudo().create({
            'filename': 'FoliosSII76201224333%s.xml' % start,
            'caf_file': cls._make_caf_file(
                ('<TD></TD>', '<TD>33</TD>'),
                ('<RNG><D>001</D><H>100</H></RNG>', '<RNG><D>%s</D><H>%s</H></RNG>' % (start, end)),
            ),
            'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_a_f_dte').id,
            'company_id': cls.branch_b.id,
            'status': 'in_use',
        }) for start, end in ((400, 401), (402, 403))]

    def _post_invoice(self, company):
        """Post an invoice of document type 33 in ``company`` and return it."""
        return self._create_invoice_one_line(
            post=True,
            invoice_date='2019-10-23',
            price_unit=1000.0,
            product_id=self.product_a,
            tax_ids=self.tax_19,
            partner_id=self.partner_sii,
            company_id=company,
            journal_id=self.branch_journals.get(company, self.sale_journal),
            currency_id=self.env.ref('base.CLP'),
            l10n_latam_document_type_id=self.env.ref('l10n_cl.dc_a_f_dte'),
        )

    def test_branch_without_a_caf_continues_the_series_of_its_parent(self):
        self.assertEqual(self._post_invoice(self.parent_company).name, 'FAC 000001')
        self.assertEqual(self._post_invoice(self.branch_a).name, 'FAC 000002')

    def test_branch_spends_its_own_ranges_in_turn_and_never_falls_back(self):
        self.assertEqual(
            [self._post_invoice(self.branch_b).name for _ in range(4)],
            ['FAC 000400', 'FAC 000401', 'FAC 000402', 'FAC 000403'],
        )
        self.assertEqual(self.caf_b_first.status, 'spent')
        self.assertEqual(self.caf_b_second.status, 'spent')
        # the parent still has folios left, but a branch granted its own range is blocked instead
        with self.assertRaisesRegex(UserError, 'CAF'):
            self._post_invoice(self.branch_b)

    def test_branch_signs_and_issues_under_the_rut_of_its_parent(self):
        self.assertEqual(self.branch_a._l10n_cl_get_root_company(), self.parent_company)
        self.assertEqual(self.branch_a.sudo()._get_digital_signature(), self.certificate)
        dte = self._post_invoice(self.branch_a).l10n_cl_dte_file.raw.decode('ISO-8859-1')
        self.assertIn('<RUTEmisor>76201224-3</RUTEmisor>', dte)
        # the branch is where the document is issued from, so it keeps its own address
        self.assertIn('<CmnaOrigen>Les Condes</CmnaOrigen>', dte)
