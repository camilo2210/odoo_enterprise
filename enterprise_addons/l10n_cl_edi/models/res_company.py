# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, misc
from odoo.tools.translate import _


L10N_CL_SII_REGIONAL_OFFICES_ITEMS = [
    ('ur_Alt', 'Alto Hospicio'),
    ('ur_Anc', 'Ancud'),
    ('ur_Ang', 'Angol'),
    ('ur_Ant', 'Antofagasta'),
    ('ur_Ari', 'Arica y Parinacota'),
    ('ur_Ays', 'Aysén'),
    ('ur_Buin', 'Buin'),
    ('ur_Cal', 'Calama'),
    ('ur_Cas', 'Castro'),
    ('ur_Cau', 'Cauquenes'),
    ('ur_Cha', 'Chaitén'),
    ('ur_Chn', 'Chañaral'),
    ('ur_ChC', 'Chile Chico'),
    ('ur_Chi', 'Chillán'),
    ('ur_Coc', 'Cochrane'),
    ('ur_Cop', 'Concepción '),
    ('ur_Cos', 'Constitución'),
    ('ur_Coo', 'Copiapo'),
    ('ur_Coq', 'Coquimbo'),
    ('ur_Coy', 'Coyhaique'),
    ('ur_Cur', 'Curicó'),
    ('ur_Ill', 'Illapel'),
    ('ur_Iqu', 'Iquique'),
    ('ur_LaF', 'La Florida'),
    ('ur_LaL', 'La Ligua'),
    ('ur_LaS', 'La Serena'),
    ('ur_LaU', 'La Unión'),
    ('ur_Lan', 'Lanco'),
    ('ur_Leb', 'Lebu'),
    ('ur_Lin', 'Linares'),
    ('ur_Lod', 'Los Andes'),
    ('ur_Log', 'Los Ángeles'),
    ('ur_LosRios', 'Los Ríos'),
    ('ur_Nunoa', 'Ñuñoa'),
    ('ur_Maipu', 'Maipu'),
    ('ur_Melipilla', 'Melipilla'),
    ('ur_Oso', 'Osorno'),
    ('ur_Ova', 'Ovalle'),
    ('ur_Pan', 'Panguipulli'),
    ('ur_Par', 'Parral'),
    ('ur_Pic', 'Pichilemu'),
    ('ur_Por', 'Porvenir'),
    ('ur_PuM', 'Puerto Montt'),
    ('ur_PuN', 'Puerto Natales'),
    ('ur_PuV', 'Puerto Varas'),
    ('ur_PuA', 'Punta Arenas'),
    ('ur_Qui', 'Quillota'),
    ('ur_Ran', 'Rancagua'),
    ('ur_SaA', 'San Antonio'),
    ('ur_SanBernardo', 'San Bernardo'),
    ('ur_Sar', 'San Carlos'),
    ('ur_SaF', 'San Felipe'),
    ('ur_SaD', 'San Fernando'),
    ('ur_SaV', 'San Vicente de Tagua Tagua'),
    ('ur_SaZ', 'Santa Cruz'),
    ('ur_SaC', 'Santiago Centro'),
    ('ur_SaN', 'Santiago Norte'),
    ('ur_SaO', 'Santiago Oriente'),
    ('ur_SaP', 'Santiago Poniente'),
    ('ur_SaS', 'Santiago Sur'),
    ('ur_TaT', 'Tal-Tal'),
    ('ur_Tac', 'Talca'),
    ('ur_Tah', 'Talcahuano'),
    ('ur_Tem', 'Temuco'),
    ('ur_Toc', 'Tocopilla'),
    ('ur_Vld', 'Valdivia'),
    ('ur_Val', 'Vallenar'),
    ('ur_Vlp', 'Valparaíso'),
    ('ur_Vic', 'Victoria'),
    ('ur_ViA', 'Villa Alemana'),
    ('ur_ViR', 'Villarrica'),
    ('ur_ViM', 'Viña del Mar'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_cl_dte_email = fields.Char('DTE Email', related='partner_id.l10n_cl_dte_email', readonly=False)
    l10n_cl_internal_identifier = fields.Char(
        'Internal Identifier',
        help="Code your trading partners put in the SII 'CdgIntRecep' field (field 51, max. 20 characters) to "
             "identify this branch. Incoming documents are routed to the branch whose identifier matches it.")
    l10n_cl_dte_service_provider = fields.Selection([
        ('SIITEST', 'SII - Test'),
        ('SII', 'SII - Production'),
        ('SIIDEMO', 'SII - Demo Mode'),
    ], 'DTE Service Provider',
        help="Please select your company service provider for DTE service.")
    l10n_cl_dte_resolution_number = fields.Char(
        'SII Exempt Resolution Number',
        help='This value must be provided and must appear in your pdf or printed tribute document, under the '
             'electronic stamp to be legally valid.')
    l10n_cl_dte_resolution_date = fields.Date('SII Exempt Resolution Date')
    l10n_cl_sii_regional_office = fields.Selection(
        L10N_CL_SII_REGIONAL_OFFICES_ITEMS, translate=False, string='SII Regional Office')
    l10n_cl_company_activity_ids = fields.Many2many('l10n_cl.company.activities', string='Activities Names',
        help='Please select the SII registered economic activities codes for the company', readonly=False)
    l10n_cl_sii_taxpayer_type = fields.Selection(
        related='partner_id.l10n_cl_sii_taxpayer_type', index=True, readonly=False,
        help='1 - VAT Affected (1st Category) (Most of the cases)\n'
             '2 - Fees Receipt Issuer (Applies to suppliers who issue fees receipt)\n'
             '3 - End consumer (only receipts)\n'
             '4 - Foreigner')
    l10n_cl_certificate_ids = fields.One2many(
        'certificate.certificate', 'company_id', string='Certificates (CL)')
    l10n_cl_is_there_shared_certificate = fields.Boolean('Is There Shared Certificate?', compute='_compute_is_there_shared_cert')

    def _l10n_cl_get_root_company(self):
        """The legal entity this company issues under: itself if it declares a RUT, else the closest one that does."""
        self.ensure_one()
        # sudo: the ancestors up to the RUT bearer are needed even if unallowed to the user
        company = self.sudo()
        return next((parent for parent in company.parent_ids[::-1] if parent.vat), company.root_id)

    def _l10n_cl_get_rut_companies(self):
        """Every company issuing under this one's RUT: its legal entity and the branches trading under it."""
        root = self._l10n_cl_get_root_company()
        # a branch declaring a RUT is another taxpayer, and so is every branch under it
        return self.env['res.company'].sudo().with_context(active_test=False).search(
            [('id', 'child_of', root.id)],
        ).filtered(lambda company: company._l10n_cl_get_root_company() == root)

    def _l10n_cl_get_cafs(self, document_type):
        """The CAF ranges of ``document_type`` this company draws folios from, spent ones included, lowest first."""
        self.ensure_one()
        root = self._l10n_cl_get_root_company()
        cafs = self.env['l10n_cl.dte.caf'].sudo().search([
            ('l10n_latam_document_type_id', '=', document_type.id),
            ('company_id', 'in', (self | root).ids),
        ], order='start_nb, id')
        # a company ever granted a range of its own never draws on the one above, spent or not
        return cafs.filtered(lambda caf: caf.company_id == (self if self in cafs.company_id else root))

    def _l10n_cl_get_active_caf(self, document_type):
        """The range the next folio of ``document_type`` comes from, empty once this company has spent them all."""
        return self._l10n_cl_get_cafs(document_type).filtered(lambda caf: caf.status == 'in_use')[:1]

    def _get_company_root_delegated_field_names(self):
        # EXTENDS 'base': a branch shares the SII registration of its parent
        return super()._get_company_root_delegated_field_names() + [
            'l10n_cl_dte_service_provider',
            'l10n_cl_dte_resolution_number',
            'l10n_cl_dte_resolution_date',
            'l10n_cl_sii_regional_office',
            'l10n_cl_company_activity_ids',
        ]

    def _prepare_cl_demo_objects(self):
        for c in self:
            if c.l10n_cl_dte_service_provider == 'SIIDEMO':
                c._create_demo_caf_files()
                sales_journals = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(c),
                    ('type', '=', 'sale'), ('l10n_latam_use_documents', '=', True),
                ])
                for sj in sales_journals:
                    sj.l10n_cl_point_of_sale_type = 'online'

    def _create_demo_caf_files(self, enabled_dte_documents=False):
        self.ensure_one()
        if not self.vat:
            raise UserError(_('To create demo CAF files, you must define the company VAT first.'))
        with misc.file_open('l10n_cl_edi/tests/template/caf_file_template.xml') as f:
            caf_file_template = f.read()
        today_string_date = fields.Date.to_string(fields.Date.context_today(
            self.with_context(tz='America/Santiago')))
        caf_file_template = caf_file_template. \
            replace('76201224-3', self.vat). \
            replace('Blanco Martin Asociados EIRL', self.name). \
            replace('<D>001</D><H>100</H>', '<D>1</D><H>499999</H>'). \
            replace('<IDK>100</IDK>', '<IDK>999999</IDK>'). \
            replace('2019-10-22', today_string_date)
        if not enabled_dte_documents:
            enabled_dte_documents = self.env['l10n_latam.document.type'].search(
                ['|', ('code', 'in', [52, 110, 111, 112]), ('l10n_cl_active', '=', True),
                 ('country_id.code', '=', 'CL')])
        existing_caf_files = self.env['l10n_cl.dte.caf'].search([
            ('company_id', 'in', self._l10n_cl_get_rut_companies().ids),
        ]).mapped('l10n_latam_document_type_id.code')
        for dte_caf in enabled_dte_documents:
            if dte_caf.code in existing_caf_files:
                continue
            caf_file = caf_file_template.replace('<TD></TD>', '<TD>%s</TD>' % dte_caf.code)
            caf_id = self.env['l10n_cl.dte.caf'].sudo().create({
                'filename': ('FoliosSII%s%s%sDEMO1.xml' % (self.vat, today_string_date, dte_caf.code)).replace('-', ''),
                'caf_file': BinaryBytes(caf_file.encode('utf-8')),
                'l10n_latam_document_type_id': dte_caf.id,
                'status': 'in_use',
                'company_id': self.id,
            })
            caf_file = caf_file.replace('<D>1</D><H>499999</H>', '<D>500000</D><H>999999</H>')
            caf_id.copy({
                'filename': ('FoliosSII%s%s%sDEMO2.xml' % (self.vat, today_string_date, dte_caf.code)).replace('-', ''),
                'caf_file': BinaryBytes(caf_file.encode('utf-8')),
            })

    def _get_digital_signature(self, user_id=None):
        """
        This method looks for a digital signature that could be used to sign invoices for the current company.
        If the digital signature is intended to be used exclusively by a single user, it will have that user_id
        otherwise, if the user is false, it is understood that the owner of the signature (which is always
        a natural person) shares it with the rest of the users for that company.
        """
        for company in self | self._l10n_cl_get_root_company():
            certificates = company.l10n_cl_certificate_ids.filtered('is_valid')
            if user_id is not None and (owned := certificates.filtered(lambda c: c.user_id.id == user_id)):
                return owned[0]
            if shared := certificates.filtered(lambda c: not c.user_id):
                return shared[0]
        raise UserError(self.env._('There is not a valid certificate for the company: %(company_name)s', company_name=self.name))

    @api.constrains('l10n_cl_company_activity_ids')
    def _check_l10n_cl_company_activity_ids_limit(self):
        for company in self:
            if len(company.l10n_cl_company_activity_ids) > 4:
                raise ValidationError(self.env._(
                    "The maximum amount of Activities Names is 4. Please select only 4 or less options."
                ))

    @api.depends('l10n_cl_dte_service_provider', 'parent_id')
    def _compute_is_there_shared_cert(self):
        cl_certificate = self.env['certificate.certificate']
        for company in self:
            root_origin = company._l10n_cl_get_root_company()._origin
            company.l10n_cl_is_there_shared_certificate = bool(root_origin) and bool(cl_certificate.search(
                [('user_id', '=', False), ('company_id', '=', root_origin.id)], limit=1))
