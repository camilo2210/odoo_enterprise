# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

from odoo.addons.l10n_br_avatax.models.product_template import (
    SOURCE_ORIGIN_SELECTION,
    SPED_TYPE_SELECTION,
    USE_TYPE_SELECTION,
)


class L10n_BrOperationType(models.Model):
    _name = 'l10n_br.operation.type'
    _description = "Operation Type"

    active = fields.Boolean(default=True)
    technical_name = fields.Char(
        required=True,
        string="Technical Name",
        help="The name that will be sent as operationType to the Brazilian Avatax API.",
    )
    name = fields.Char(
        required=True,
        string="Name",
        translate=True,
    )

    # Issuer Options
    l10n_br_issuer_manufacturer_industry_equivalent = fields.Boolean(
        string="Is Industry",
        help="Brazil: Item is merchandise but will be considered as a product. And the issuer will be considered as an Industry.",
    )
    l10n_br_issuer_appropriate_ipi_credit = fields.Boolean(
        string="Appropriate IPI Credit",
        help="Brazil: Informs that this item will have rights to appropriate IPI credit.",
    )
    l10n_br_issuer_not_subject_to_icmsst = fields.Boolean(
        string="Not Subjected To ICMS ST",
        help="Brazil: Item is not subject to ICMS ST, even though it has CEST, example, fixed assets, used products like cars.",
    )
    l10n_br_issuer_is_icmsst_substitute = fields.Boolean(
        string="Issuer Is ICMS ST Substitute",
        help="Brazil: ICMS substitute flag that identifies the wholesaler, retailer, distributor roles.",
    )
    l10n_br_issuer_appropriate_icms_credit = fields.Boolean(
        string="Appropriate ICMS Credit",
        help="Brazil: Informs that this item will have rights to appropriate ICMS credit.",
    )
    l10n_br_issuer_appropriate_piscofins_credit = fields.Boolean(
        string="Appropriate PIS/COFINS Credit",
        help="Brazil: Subject to appropriate PIS/COFINS credit, when it is non-cumulative.",
    )

    # Recipient Options
    l10n_br_recipient_manufacturer_industry_equivalent = fields.Boolean(
        string="Equivalent To Manufacturer Or Industry",
        help="Brazil: This attribute is used only on Inbound Scenarios, and when active, the item is considered the own Production of the Entity (Example: Vendor).",
    )
    l10n_br_recipient_is_icmsst_substitute = fields.Selection(
        string="Recipient Is ICMS ST Substitute",
        selection=[
            ('default', "Default"),
            ('yes', "Yes"),
            ('no', "No"),
        ],
        help="""Brazil: Force the entity to play or not a tax collector role for ICMS-ST Substitute.
        - Default: ICMS ST is not Applicable.
        - Yes: Entity is ICMS ST Substitute.
        - No: Entity is not ICMS ST Substitute.""",
    )

    # Product Options
    l10n_br_source_origin = fields.Selection(
        SOURCE_ORIGIN_SELECTION,
        string='Source of Origin',
        help='Brazil: Product Source of Origin indicates if the product has a foreign or national origin with different variations and characteristics depending on the product use case. If left empty, the value configured on each product is used.',
    )
    l10n_br_sped_type = fields.Selection(
        SPED_TYPE_SELECTION,
        string='SPED Fiscal Product Type',
        help='Brazil: Fiscal product type according to SPED list table. If left empty, the value configured on each product is used.',
    )
    l10n_br_use_type = fields.Selection(
        USE_TYPE_SELECTION,
        string='Purpose of Use',
        help='Brazil: indicate what is the usage purpose for this product. If left empty, the value configured in the document is used, and if empty on the document, the value configured on each product is used.',
    )
