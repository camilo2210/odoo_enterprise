import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Tag id should be a 17 characters string composed of a letter followed by 16 digits
PRICER_TAG_ID_LENGTH = 17


class PricerTag(models.Model):
    _name = "pricer.tag"
    _description = "Pricer electronic tag"

    name = fields.Char(
        string="Pricer Tag Barcode",
        help="It is recommended to use a barcode scanner for input",
        required=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Associated Product",
        required=True,
        index=True,
        ondelete="cascade",
    )
    pricer_store_id = fields.Many2one(
        comodel_name="pricer.store",
        string="Associated Pricer Store",
        required=True,
        ondelete="cascade",
        index="btree_not_null",
    )

    # When we create a new pricer tag, it needs to be linked to its associated product
    needs_pricer_product_link = fields.Boolean(default=True)

    # ------------------------- CONSTRAINS -------------------------

    # Avoid creating multiple Pricer tags with the same id
    _name_unique = models.Constraint(
        "unique (name)",
        "A Pricer tag with this barcode id already exists",
    )

    @api.constrains("name")
    def _check_tag_id(self):
        """
        Tag id should be a 17 characters string composed of a letter followed by 16 digits
        [LETTER][16 digits]

        Examples:
        N4081315787313278
        B4093233954716057
        A4073091573616030
        """
        for record in self:
            tag_id = record.name
            if (
                len(tag_id) != PRICER_TAG_ID_LENGTH
                or not tag_id[0].isalpha()
                or not tag_id[1:].isdigit()
            ):
                raise ValidationError(
                    _(
                        "Tag id should be composed of a letter followed by 16 digits (e.g. N4081315787313278)"
                    )
                )

    # ------------------------- ODOO METHODS -------------------------

    def write(self, vals):
        """If the product associated to this tag or the name
        of the tag (the barcode) has been changed, we mark the tag
        as needing to be relinked to its associated product in Pricer
        """
        vals["needs_pricer_product_link"] = "product_id" in vals or "name" in vals
        if "product_id" in vals:
            self.env["product.product"].browse(
                vals["product_id"]
            ).needs_pricer_update = True
        return super().write(vals)

    # ------------------------- PRICER API METHODS -------------------------

    @api.ondelete(at_uninstall=True)
    def _unlink_product_on_delete(self):
        """
        When we delete a Pricer tag / unlink it from a product
        --> unlink it from the associated Pricer store
        --> stop displaying the linked product on it directly
        """
        for record in self:
            record.pricer_store_id.unlink_label(record.name)

    def _get_link_body(self):
        """Get the JSON related to a link request for this tag"""
        return [
            {
                "barcode": tag.name,
                "links": [
                    {
                        "barcode": tag.name,
                        "itemId": tag.product_id.id,
                    }
                ],
            }
            for tag in self
        ]
