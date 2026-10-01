from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    auto_sale_order_line_id = fields.Many2one('sale.order.line', string="Intercompany Sale Order Line", readonly=True, copy=False, index='btree_not_null')

    def write(self, vals):
        if not self.env.context.get('skip_intercompany_sync') and self._contains_intercompany_sync_vals(vals):
            if 'name' in vals:
                display_type_desc = {type_desc[0]: type_desc[1] for type_desc in self._fields['display_type']._description_selection(self.env)}
            # propagate changes to the linked sale order line if any
            discount_digits = self.env['decimal.precision'].precision_get('Discount')
            display_uom = self.env.user.has_group('uom.group_uom')
            changes_to_log = defaultdict(lambda: defaultdict(list))  # dict((po_id_to_so): dict(product: list(changes))), because we need a message per so
            for pol in self:
                if sol := pol.sudo().auto_sale_order_line_id:
                    po_id = pol.order_id.id
                    so = sol.order_id
                    sol_vals = {}
                    if 'product_qty' in vals and pol.uom_id.compare(pol.product_qty, vals['product_qty']) != 0:
                        sol_vals['product_uom_qty'] = pol.uom_id._compute_quantity(vals['product_qty'], sol.product_uom_id)
                        changes_to_log[po_id, so][pol.product_id].append({'field_label': self._fields['product_qty'].string, 'old_value': pol.product_qty, 'new_value': display_uom and str(vals['product_qty']) + " " + pol.uom_id.display_name or vals['product_qty']})
                    if 'price_unit' in vals and pol.price_unit != vals['price_unit']:  # price_unit has a "min precision unit" instead of a precision unit
                        # currency is consistent between PO/SO
                        sol_vals['price_unit'] = pol.uom_id._compute_price(vals['price_unit'], sol.product_uom_id)
                        changes_to_log[po_id, so][pol.product_id].append({'field_label': self._fields['price_unit'].string, 'old_value': pol.price_unit, 'new_value': vals['price_unit']})
                    if 'discount' in vals and float_compare(pol.discount, vals['discount'], precision_digits=discount_digits) != 0:
                        sol_vals['discount'] = vals['discount']
                        changes_to_log[po_id, so][pol.product_id].append({'field_label': self._fields['discount'].string, 'old_value': pol.discount, 'new_value': vals['discount']})
                    if pol.display_type and 'name' in vals:
                        sol_vals['name'] = vals['name']
                        changes_to_log[po_id, so][pol.product_id].append({'field_label': display_type_desc[pol.display_type], 'old_value': pol.name, 'new_value': vals['name']})
                    if sol_vals:
                        sol.sudo().with_company(sol.company_id).with_context(skip_intercompany_sync=True).write(sol_vals)
            if changes_to_log:
                for (po_id, so), products_to_changes in changes_to_log.items():
                    if not so:
                        continue
                    values = {
                        'partner_id': so.user_id.partner_id,
                        'updated_po': po_id,
                        'products_to_changes': products_to_changes
                    }
                    so.message_post_with_source(
                        'sale_purchase_inter_company_rules.updated_vals_interco_so_po',
                        render_values=values,
                        partner_ids=so.user_id.partner_id.ids,
                        subtype_xmlid='mail.mt_note',
                    )
        return super().write(vals)

    @api.model
    def _contains_intercompany_sync_vals(self, vals):
        return any(val in vals for val in ['product_qty', 'price_unit', 'discount', 'name'])
