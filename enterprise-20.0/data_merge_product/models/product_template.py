# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _merge_method(self, destination, source):
        """
        Prevent direct template merge for products with variants.

        Checks each template in destination/source and raises a UserError if it
        has more than one variant or any valid attribute lines, since variant level
        merge must be used instead.

        :param destination: The destination product template record to merge into.
        :param source: The source product template record to merge from.
        """
        all_records = destination + source

        for record in all_records:
            if len(record.product_variant_ids.filtered('active')) != 1 or record.valid_product_template_attribute_line_ids:
                return {
                    'error': self.env._(
                        'Direct merging is unavailable for products with variants.\n'
                        'Please merge the individual variants instead'
                    )
                }
        # When merging single variant templates, the generic merge tries to move the source variant to the
        # destination template, violating the unique constraint _combination_unique.
        # To bypass this, we archive duplicate source variant before the generic merge runs,
        # allowing the merge to proceed smoothly without hitting the constraint.
        dest_variant = destination.product_variant_ids.filtered('active')

        # Collect and archive all source variants at once
        source_variants = source.product_variant_ids.filtered('active')
        source_variants.active = False

        # Merge variants first so their references move to the destination variant before the templates are merged.
        # This keeps template merge from breaking because the variant link has already been fixed.
        self.env['data_merge.group']._merge_method(dest_variant, source_variants)

        return self.env['data_merge.group']._merge_method(destination, source)
