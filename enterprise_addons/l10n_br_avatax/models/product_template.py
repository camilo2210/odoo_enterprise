# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

USE_TYPE_SELECTION = [
    ('use or consumption', 'Use or consumption'),
    ('resale', 'Resale'),
    ('agricultural production', 'Agricultural production'),
    ('production', 'Production'),
    ('fixed assets', 'Fixed assets'),
    ('notApplicable', 'Not applicable'),
]

SOURCE_ORIGIN_SELECTION = [
    ('0', 'National goods - except those treated in codes 3,4, 5 and 8'),
    ('1', 'Foreign goods - Imported directly by seller, except those in code 6'),
    ('2', 'Foreign goods - Acquired in the internal market (inside Brazil), except those in code 7'),
    ('3', 'National goods - Merchandise or goods with imported content above 40% and with less than or equal to 70%'),
    ('4',
     'National goods from production following \'standard basic processes\' as stablished by legislation (standard basic processes are devised to separate simple assembly from manufaturing processes)'),
    ('5', 'National goods - Merchandise or goods with imported content equal or below 40%'),
    ('6',
     'Foreign goods - Directly imported by Seller, without a National Equivalent as listed by Comex and natural gas'),
    ('7', 'Foreign goods - Acquired inside Brazil, without a National Equivalent as listed by Comex and natural gas'),
    ('8', 'National goods - Merchandise or goods with imported content above 70% (pt)'),
]

SPED_TYPE_SELECTION = [
    ('FOR MERCHANDISE', '00 - Merchandise for Resale'),
    ('FEEDSTOCK', '01 - Raw Material'),
    ('PACKAGING', '02 - Packaging'),
    ('PRODUCT IN PROCESS', '03 - Product in Process'),
    ('FOR PRODUCT', '04 - Finished Product'),
    ('SUBPRODUCT', '05 - Byproduct'),
    ('INTERMEDIATE PRODUCT', '06 - Intermediate Product'),
    ('MATERIAL FOR USAGE AND CONSUMPTION', '07 - Material for Use and Consumption'),
    ('FIXED ASSETS', '08 - Fixed Assets'),
    ('SERVICE', '09 - Service'),
    ('OTHER INPUTS', '10 - Other Inputs'),
    ('NO RESTRICTION', '99 - Others'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _l10n_br_property_service_code_origin_id_domain(self):
        return [("city_id", "=", self.env.company.partner_id.sudo().city_id.id)]

    l10n_br_cest_code = fields.Char(
        string='CEST Code',
        help='A tax classification code used to identify goods and products subject to tax substitution under ICMS regulations.'
             'It helps determine the applicable tax treatment and procedures for specific items.'
             'Check if your product is subject or not to this in https://www.codigocest.com.br/.'
    )
    l10n_br_ncm_code_id = fields.Many2one('l10n_br.ncm.code', string="Mercosul NCM Code", help="Brazil: Use this field to specify the classification code of the item, either the NCM (Nomenclatura Comum do Mercosul) for goods or the LC116 for services.")
    l10n_br_property_service_code_origin_id = fields.Many2one(
        "l10n_br.service.code",
        domain=_l10n_br_property_service_code_origin_id_domain,
        string="Service Code Origin",
        company_dependent=True,
        help="Brazil: City service code where the provider is registered.",
    )
    l10n_br_labor = fields.Boolean(
        "Labor Assignment", help="Brazil: If your service involves labor, select this checkbox."
    )
    l10n_br_service_code_ids = fields.Many2many(
        "l10n_br.service.code",
        string="Service Codes",
        help="Brazil: The service codes for this product, as defined by the cities in which you wish to sell it. If no city-specific code is provided, the Service Code Origin will be used instead.",
    )
    l10n_br_company_city_id = fields.Many2one(
        "res.city",
        compute="_compute_l10n_br_company_city_id",
        help="Technical field used to determined the default of a service code when configured as a service code origin.",
    )

    # technical names of these selections fields are directly passed to the API
    l10n_br_source_origin = fields.Selection(SOURCE_ORIGIN_SELECTION,
        string='Source of Origin',
        help='Brazil: Product Source of Origin indicates if the product has a foreign or national origin with different variations and characteristics depending on the product use case'
    )
    l10n_br_sped_type = fields.Selection(SPED_TYPE_SELECTION, string='SPED Fiscal Product Type', help='Brazil: Fiscal product type according to SPED list table')
    l10n_br_use_type = fields.Selection(USE_TYPE_SELECTION, string='Purpose of Use', help='Brazil: indicate what is the usage purpose for this product')
    l10n_br_transport_cost_type = fields.Selection([
        ('freight', 'Freight'),
        ('insurance', 'Insurance'),
        ('other', 'Other costs')
    ], string='Additional Cost Type', help='Brazil: select whether this product will be use to register Freight, Insurance or Other Costs amounts related to the transaction.')

    @api.constrains("l10n_br_service_code_ids")
    def _check_l10n_br_service_code_ids(self):
        for product in self:
            for (_company, city), codes in product.l10n_br_service_code_ids.grouped(lambda code: (code.company_id, code.city_id)).items():
                if len(codes) > 1:
                    raise ValidationError(_("Can't have more than one service code for %s.", city.display_name))

    @api.depends("company_id")
    @api.depends_context("company")
    def _compute_l10n_br_company_city_id(self):
        for product in self:
            company = product.company_id or self.env.company
            product.l10n_br_company_city_id = company.partner_id.city_id

    def _l10n_br_is_only_allowed_on_service_invoice(self):
        """Service products are only allowed on a goods invoice if it's a transportation service."""
        return not self.l10n_br_transport_cost_type and self.type == "service"
