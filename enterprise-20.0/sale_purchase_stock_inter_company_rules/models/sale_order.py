# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_purchase_order_data(self, company, company_partner, direct_delivery_address):
        res = super()._prepare_purchase_order_data(company, company_partner, direct_delivery_address)
        # find location and warehouse, pick warehouse from company object
        warehouse = self.env['stock.warehouse'].search([('partner_id', 'parent_of', direct_delivery_address.id)], limit=1)
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if not warehouse:
            raise UserError(
                _('Configure correct warehouse for company(%s) from Menu: Settings/Users/Companies', company.name))
        is_interbranch = self.company_id.parent_id and self.company_id.parent_id.id == company.parent_id.id
        picking_type_id = self.env['stock.picking.type'].sudo().search([
            ('warehouse_id', '=', warehouse.id), ('code', '=', 'incoming'),
            ('default_location_src_id.usage', '=', 'transit'), ('default_location_src_id.company_id', '=', company.parent_id.id if is_interbranch else False)
        ], limit=1)
        if not picking_type_id:
            picking_type_id = self.env['stock.picking.type'].sudo().search([
                ('code', '=', 'incoming'), ('warehouse_id', '=', warehouse.id)
            ], limit=1)
        if not picking_type_id:
            picking_type_id = self.env['purchase.order'].with_user(SUPERUSER_ID)._default_picking_type()

        res['picking_type_id'] = picking_type_id.id

        return res

    def _get_purchase_order_partner(self, user=False):
        self.ensure_one()
        return self.warehouse_id.partner_id or super()._get_purchase_order_partner(user)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_location_final(self):
        partner_company = self.env['res.company']._find_company_from_partner(self.order_id.partner_id.id)
        if partner_company and partner_company != self.company_id and self.order_id.partner_id != self.order_id.partner_shipping_id:
            # Means that's we're in inter-company transaction -> Must sent to inter-company transit.
            return self.order_id.partner_id.property_stock_customer
        return super()._get_location_final()
