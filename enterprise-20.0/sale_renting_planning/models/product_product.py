# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.depends("product_tmpl_id.planning_role_id.resource_ids")
    @api.depends_context("in_rental_schedule")
    def _compute_display_name(self):
        super()._compute_display_name()

        if self.env.context.get("in_rental_schedule"):
            template_res_count = {}
            for product in self:
                template = product.product_tmpl_id
                if template not in template_res_count:
                    template_res_count[template] = len(template.planning_role_id.resource_ids)

                resource_count = template_res_count[template]
                if resource_count == 1:
                    product.display_name = self.env._(
                        "%(product)s (1 resource)",
                        product=product.display_name,
                    )
                elif resource_count > 1:
                    product.display_name = self.env._(
                        "%(product)s (%(count)i resources)",
                        product=product.display_name,
                        count=resource_count,
                    )
