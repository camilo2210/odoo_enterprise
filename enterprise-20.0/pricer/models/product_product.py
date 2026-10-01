import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

PRICER_RELATED_FIELDS = [
    "additional_product_tag_ids",
    "barcode",
    "currency_id",
    "list_price",
    "lst_price",
    "name",
    "on_sale_price",
    "pricer_tag_ids",
    "pricer_store_id",
    "pricer_tags_pricelist_id",
    "on_sale_price",
    "res.partner",
    "seller_ids",
    "stock",
    "taxes_id",
    "to_weight",
    "weight",
]


class ProductProduct(models.Model):
    """Adding the necessary fields to products to use with Pricer electronic tags"""

    _inherit = "product.product"

    pricer_store_id = fields.Many2one(
        comodel_name="pricer.store",
        help="This product will be linked to and displayed on the Pricer tags of the store selected here",
        related="pricer_tag_ids.pricer_store_id",
    )
    pricer_tag_ids = fields.One2many(
        comodel_name="pricer.tag",
        inverse_name="product_id",
        string="Pricer tags ids",
        help="This product will be linked to and displayed on the Pricer tags with ids listed here. It is recommended to use a barcode scanner",
    )

    # Boolean to checker whether we need to create/update this product in Pricer db
    needs_pricer_update = fields.Boolean(default=False)

    # String representing price including taxes
    # Used in requests sent to the Pricer API and displayed on tags
    pricer_display_price = fields.Char()

    pricer_tags_pricelist_id = fields.Many2one(
        "product.pricelist",
        help="This pricelist will be used to set sales on Pricer tags for this product",
        domain=lambda self: [
            "&",
            ("item_ids.product_id", "=", self.id),
            "&",
            ("item_ids.min_quantity", "<=", 1),
            "|",
            "|",
            ("item_ids.compute_price", "=", "fixed"),
            ("item_ids.is_plain_discount", "=", True),
            ("item_ids.base", "in", ["list_price", "standard_price"]),
        ],
        # for now, we don't handle pricelists available for quantities > 1, neither those based on 'formulas based on
        # other pricelists'
    )

    on_sale_price = fields.Float(
        help="Price after setting a Pricer Sales Pricelist", store=True
    )

    def compute_prices(self, on_sale=False) -> float:
        """Compute price to display depending on whether the product is
        on sale or not.
        """
        currency = self.currency_id
        price = self.on_sale_price if on_sale else self.lst_price
        if self.taxes_id:
            res = self.taxes_id.compute_all(
                price, product=self, partner=self.env["res.partner"]
            )
            total_included = res["total_included"]
            price = (
                total_included
                if currency.compare_amounts(total_included, price)
                else res["total_excluded"]
            )

        return price

    def _get_upsert_body(self):
        """
        If the product related to a pricer tag needs to be updated:
         - we need to add its data to the JSON body used in create/update request
        """
        variant = ",".join(
            [
                ",".join(record.product_attribute_value_id.mapped("name"))
                for record in self.product_template_variant_value_ids
                if record.price_extra and record.price_extra != 0
            ]
        )

        variant_tag = ",".join(
            [
                ",".join(record.mapped("name"))
                for record in self.additional_product_tag_ids
            ]
        )

        on_sale = bool(self.pricer_tags_pricelist_id)

        price = self.compute_prices(on_sale=on_sale)
        self.pricer_display_price = self.currency_id.format(price)
        weight_w_unit = f"{self.weight} {self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()}"

        # If "units of measure" setting is enabled, we compute unit price
        uom_id = self.uom_id
        price_per_unit = amount = ""
        if self.env.user.has_group("uom.group_uom") and uom_id.relative_uom_id:
            unit_price = price / uom_id.relative_factor
            price_per_unit = (
                f"{self.currency_id.format(unit_price)}/{uom_id.relative_uom_id.name}"
            )
            amount = f"{uom_id.relative_factor} {uom_id.relative_uom_id.name}"

        # If multiple suppliers / taxes are set, we only send the first one to Pricer
        supplier_id = self.seller_ids[0] if self.seller_ids else None
        taxes_id = (
            self.product_tmpl_id.taxes_id[0] if self.product_tmpl_id.taxes_id else None
        )

        data_to_send = {
            "itemId": self.id,
            "itemName": self.name,
            "price": self.pricer_display_price,
            "presentation": "PROMO"
            if on_sale
            else "NORMAL",  # template name used on pricer tags
            "properties": {
                "amount": amount,
                "barcode": self.barcode or "",
                "old_price": (
                    self.currency_id.format(self.compute_prices(on_sale=False))
                    if on_sale
                    else self.pricer_display_price
                ),
                "price_per_unit": price_per_unit,
                "price_excl_tax": self.lst_price,  # product price excluding taxes
                "stock": self.qty_available,
                "supplier_reference": supplier_id.partner_id.ref
                if supplier_id and supplier_id.partner_id
                else "",  # reference identifying the supplier
                "supplier_product_code": supplier_id.product_code
                if supplier_id
                else "",  # reference identifying the product for the supplier
                "tax_name": taxes_id.name
                if taxes_id
                else "",  # the name of the tax rule applied to the product (Ex: VAT 21%)
                "to_weight": self.to_weight or "",
                "unit_of_measure": self.uom_id.name
                if self.uom_id
                else "",  # units used to sell the product (Ex: 1.5 eur per kg)
                "variant": variant or "",
                "variant_tag": variant_tag or "",
                "weight": weight_w_unit,
            },
        }
        _logger.debug(
            "Data to send to Pricer API for product [%s] %s: %s",
            self.id,
            self.name,
            data_to_send,
        )

        return data_to_send

    def write(self, vals):
        """
        Called whenever we update a product variant and click "save"
        If Pricer related fields are changed,
        We need to send the new information to Pricer API to display it
        """
        if any(val in PRICER_RELATED_FIELDS for val in vals):
            vals["needs_pricer_update"] = True

        result = super().write(vals)
        if "pricer_store_id" in vals:
            self.pricer_tag_ids.needs_pricer_product_link = True

        return result

    @api.onchange("pricer_tags_pricelist_id", "lst_price", "standard_price")
    def _onchange_compute_pricing(self):
        # We use '._origin' to avoid getting a NewId (as the record is in a transient state) instead of id
        for product in self:
            if product.pricer_tags_pricelist_id:
                # temporarily patch _origin with dirty values so _get_product_price
                # uses the latest unsaved values
                original_lst_price = product._origin.lst_price
                original_standard_price = product._origin.standard_price

                product._origin.lst_price = product.lst_price
                product._origin.standard_price = product.standard_price
                computed_price = product.pricer_tags_pricelist_id._get_product_price(
                    product._origin or product, quantity=1.0
                )

                product._origin.lst_price = original_lst_price
                product._origin.standard_price = original_standard_price

                product.on_sale_price = product._origin.on_sale_price = computed_price
            else:
                product.on_sale_price = 0.0
