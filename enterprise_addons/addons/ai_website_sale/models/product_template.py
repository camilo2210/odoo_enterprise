# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
from odoo.http import request


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _get_website_context(self):
        """Resolve pricelist and fiscal position from the current context.
        :return: (pricelist, fiscal_position) recordsets (possibly empty)
        :rtype: tuple
        """
        return (
            self.env['product.pricelist'].sudo().browse(self.env.context.get('pricelist_id')),
            self.env['account.fiscal.position'].sudo().browse(
                self.env.context.get('fiscal_position_id'),
            ),
        )

    def _resolve_product_template_pricing(self):
        """Return website-aware sales prices for the recordset.

        :return: {tmpl_id: price_dict} or empty dict if no website
        :rtype: dict
        """
        website = self.env.website
        if not website:
            return {}
        if request and hasattr(request, 'pricelist') and hasattr(request, 'fiscal_position'):
            pricelist = request.pricelist
            fiscal_position = request.fiscal_position
        else:
            pricelist, fiscal_position = self._get_website_context()
        return self._get_sales_prices(pricelist, fiscal_position, website)

    def _ai_get_preview_metadata(self):
        """Extend preview metadata with website sales prices."""
        metadata = super()._ai_get_preview_metadata()
        prices_by_tmpl = self._resolve_product_template_pricing()
        for entry in metadata:
            entry.update(prices_by_tmpl.get(entry['id'], {}))
        return metadata

    def ai_set_main_image(self, attachment_id):
        self.ensure_one()
        self.image_1920 = self.env['ir.attachment'].browse(attachment_id).raw

    def ai_add_extra_image(self, attachment_id):
        self.ensure_one()
        attachment = self.env['ir.attachment'].browse(attachment_id)
        self.env['product.image'].create({
            'product_tmpl_id': self.id,
            'name': attachment.name,
            'image_1920': attachment.raw,
        })
