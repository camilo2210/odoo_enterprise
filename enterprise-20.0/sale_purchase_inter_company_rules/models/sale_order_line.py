from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    auto_purchase_order_line_id = fields.One2many('purchase.order.line', 'auto_sale_order_line_id', string="Intercompany Purchase Order Line", readonly=True, copy=False)  # One2One

    def write(self, vals):
        if not self.env.context.get('skip_intercompany_sync') and self._contains_intercompany_sync_vals(vals):
            if 'name' in vals:
                display_type_desc = {type_desc[0]: type_desc[1] for type_desc in self._fields['display_type']._description_selection(self.env)}
            # propagate changes to the linked purchase order line
            discount_digits = self.env['decimal.precision'].precision_get('Discount')
            display_uom = self.env.user.has_group('uom.group_uom')
            changes_to_log = defaultdict(lambda: defaultdict(list))  # dict((so_id_to_po): dict(product: list(changes))), because we need a message per po
            for sol in self:
                if pol := sol.sudo().auto_purchase_order_line_id:
                    so_id = sol.order_id.id
                    po = pol.order_id
                    pol_vals = {}
                    if 'product_uom_qty' in vals and sol.product_uom_id and sol.product_uom_id.compare(sol.product_uom_qty, vals['product_uom_qty']) != 0:
                        pol_vals['product_qty'] = sol.product_uom_id._compute_quantity(vals['product_uom_qty'], pol.uom_id)
                        changes_to_log[so_id, po][sol.product_id].append({'field_label': self._fields['product_uom_qty'].string, 'old_value': sol.product_uom_qty, 'new_value': display_uom and str(vals['product_uom_qty']) + " " + sol.product_uom_id.display_name or vals['product_uom_qty']})
                    if 'price_unit' in vals and sol.price_unit != vals['price_unit']:  # price_unit has a "min precision unit" instead of a precision unit:
                        # currency is consistent between PO/SO
                        pol_vals['price_unit'] = sol.product_uom_id._compute_price(vals['price_unit'], pol.uom_id)
                        changes_to_log[so_id, po][sol.product_id].append({'field_label': self._fields['price_unit'].string, 'old_value': sol.price_unit, 'new_value': vals['price_unit']})
                    if 'discount' in vals and float_compare(sol.discount, vals['discount'], precision_digits=discount_digits) != 0:
                        pol_vals['discount'] = vals['discount']
                        changes_to_log[so_id, po][sol.product_id].append({'field_label': self._fields['discount'].string, 'old_value': sol.discount, 'new_value': vals['discount']})
                    if sol.display_type and 'name' in vals:
                        pol_vals['name'] = vals['name']
                        changes_to_log[so_id, po][sol.product_id].append({'field_label': display_type_desc[sol.display_type], 'old_value': sol.name, 'new_value': vals['name']})
                    if pol_vals:
                        pol.sudo().with_company(pol.company_id).with_context(skip_intercompany_sync=True).write(pol_vals)
            if changes_to_log:
                for (so_id, po), products_to_changes in changes_to_log.items():
                    if not po:
                        continue
                    values = {
                        'partner_id': po.user_id.partner_id,
                        'updated_so': so_id,
                        'products_to_changes': products_to_changes
                    }
                    po.message_post_with_source(
                        'sale_purchase_inter_company_rules.updated_vals_interco_so_po',
                        render_values=values,
                        partner_ids=po.user_id.partner_id.ids,
                        subtype_xmlid='mail.mt_note',
                    )
        return super().write(vals)

    @api.model
    def _contains_intercompany_sync_vals(self, vals):
        return any(val in vals for val in ['product_uom_qty', 'price_unit', 'discount', 'name'])
