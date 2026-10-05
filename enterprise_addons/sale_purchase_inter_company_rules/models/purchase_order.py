from collections import defaultdict

from odoo import Command, SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    auto_generated = fields.Boolean(string='Auto Generated Purchase Order', copy=False)
    auto_sale_order_id = fields.Many2one('sale.order', string='Source Sales Order', readonly=True, copy=False)

    def write(self, vals):
        new_order_lines = False
        if not self.env.context.get('skip_intercompany_sync'):
            existing_order_lines = self.order_line
        res = super().write(vals)
        if not self.env.context.get('skip_intercompany_sync'):
            new_order_lines = self.order_line - existing_order_lines
        if new_order_lines:
            data = self.env['sale.order'].sudo()._read_group([('auto_purchase_order_id', 'in', new_order_lines.order_id.ids)], ['auto_purchase_order_id', 'id'])
            po_id_to_so = {po.id: so for po, so in data}
            for po in new_order_lines.order_id:
                if po.auto_sale_order_id:
                    po_id_to_so[po.id] = po.sudo().auto_sale_order_id
            if po_id_to_so:
                additions_to_log = defaultdict(lambda: self.env['purchase.order.line'])  # 1 message per so
                for order_line in new_order_lines:
                    if so := po_id_to_so.get(order_line.order_id.id):
                        additions_to_log[so] |= order_line
                if additions_to_log:
                    for so, lines in additions_to_log.items():
                        existing_sols = so.order_line
                        company_rec = self.env['res.company']._find_company_from_partner(lines.order_id.partner_id.id)  # should only be 1 PO per SO
                        sol_vals = [Command.create(self.env['purchase.order']._prepare_sale_order_line_data(line, company_rec)) for line in lines]
                        so.sudo().with_company(so.company_id).with_context(skip_intercompany_sync=True).write({'order_line': sol_vals})
                        values = {
                            'partner_id': so.user_id.partner_id,
                            'updated_po': True,
                            'lines': so.order_line - existing_sols,
                            'display_uom': self.env.user.has_group('uom.group_uom'),
                        }
                        so.message_post_with_source(
                            'sale_purchase_inter_company_rules.added_lines_interco_so_po',
                            render_values=values,
                            partner_ids=so.user_id.partner_id.ids,
                            subtype_xmlid='mail.mt_note',
                        )
        return res

    def button_approve(self, force=False):
        """ Generate inter company sales order base on conditions."""
        res = super().button_approve(force=force)
        for order in self:
            # get the company from partner then trigger action of intercompany relation
            company_rec = self.env['res.company']._find_company_from_partner(order.partner_id.id)
            if company_rec and company_rec.intercompany_generate_sales_orders and not order.auto_generated:
                order.with_user(SUPERUSER_ID).with_context(default_company_id=company_rec.id).with_company(company_rec).inter_company_create_sale_order(company_rec)
        return res

    def button_cancel(self):
        res = super().button_cancel()
        data = self.env['sale.order'].sudo()._read_group([('auto_purchase_order_id', 'in', self.ids)], ['auto_purchase_order_id', 'id'])
        po_id_to_sos = {po.id: so for po, so in data}
        for po in self:
            if so := po.auto_sale_order_id.sudo() or po_id_to_sos.get(po.id):
                values = {
                    'partner_id': so.user_id.partner_id,
                    'cancelled_po': po,
                }
                so.message_post_with_source(
                    'sale_purchase_inter_company_rules.cancelled_interco_so_po',
                    render_values=values,
                    partner_ids=so.user_id.partner_id.ids,
                    subtype_xmlid='mail.mt_note',
                )
        return res

    def inter_company_create_sale_order(self, company):
        """ Create a Sales Order from the current PO (self)
            Note : In this method, reading the current PO is done as sudo, and the creation of the derived
            SO as intercompany_user, minimizing the access right required for the trigger user.
            :param company : the company of the SO to create
        """

        for rec in self:
            # check pricelist currency should be same with SO/PO document
            company_partner = rec._get_sale_order_partner(SUPERUSER_ID)
            if company_partner.property_product_pricelist and \
               rec.currency_id.id != company_partner.property_product_pricelist.currency_id.id:
                raise UserError(_(
                    'You cannot create SO from PO because sale price list currency is different '
                    'than purchase price list currency.\n'
                    'The currency of the SO is obtained from the pricelist of the company partner.\n\n'
                    '(SO currency: %(so_currency)s, Pricelist: %(pricelist)s, Partner: %(partner)s (ID: %(id)s))',
                    so_currency=rec.currency_id.name,
                    pricelist=company_partner.property_product_pricelist.display_name,
                    partner=company_partner.display_name,
                    id=company_partner.id,
                ))

            # create the SO and generate its lines from the PO lines
            # read it as sudo, because inter-compagny user can not have the access right on PO
            sale_order_data = rec.sudo()._prepare_sale_order_data(rec.name, company_partner, company, rec.dest_address_id or rec.partner_id)

            # lines are browse as sudo to access all data required to be copied on SO line (mainly for company dependent field like taxes)
            for line in rec.order_line.sudo():
                sale_order_data['order_line'] += [(0, 0, rec._prepare_sale_order_line_data(line, company))]
            rec._set_pcavs_from_order(sale_order_data['order_line'])
            sale_order = self.env['sale.order'].with_context(allowed_company_ids=company.ids).with_user(SUPERUSER_ID).create(sale_order_data)
            msg = _("Automatically generated from %(origin)s of company %(company)s.", origin=self.name, company=rec.company_id.name)
            sale_order.message_post(body=msg)

            # write vendor reference field on PO
            if not rec.partner_ref:
                rec.partner_ref = sale_order.name

            # Validation of sales order
            if company.intercompany_document_state == 'posted':
                sale_order.with_user(SUPERUSER_ID).action_confirm()

    def _get_sale_order_partner(self, user=False):
        self.ensure_one()
        return self.company_id.partner_id.with_user(user)

    def _prepare_sale_order_data(self, name, partner, company, direct_delivery_address):
        """ Generate the Sales Order values from the PO
            :param name : the origin client reference
            :rtype name : string
            :param partner : the partner reprenseting the company
            :rtype partner : res.partner record
            :param company : the company of the created SO
            :rtype company : res.company record
            :param direct_delivery_address : the address of the SO
            :rtype direct_delivery_address : res.partner record
        """
        self.ensure_one()
        partner_addr = partner.sudo().address_get(['invoice', 'delivery', 'contact'])

        return {
            'company_id': company.id,
            'client_order_ref': name,
            'partner_id': partner.id,
            'pricelist_id': partner.property_product_pricelist.id,
            'partner_invoice_id': partner_addr['invoice'],
            'date_order': self.date_order,
            'fiscal_position_id': self.env['account.fiscal.position']._get_fiscal_position(partner).id,
            'payment_term_id': partner.property_payment_term_id.id,
            'user_id': SUPERUSER_ID,
            'auto_generated': True,
            'auto_purchase_order_id': self.id,
            'partner_shipping_id': direct_delivery_address.id or partner_addr['delivery'],
            'commitment_date': self.date_planned,
            'order_line': [],
        }

    @api.model
    def _prepare_sale_order_line_data(self, line, company):
        """ Generate the Sales Order Line values from the PO line
            :param line : the origin Purchase Order Line
            :rtype line : purchase.order.line record
            :param company : the company of the created SO
            :rtype company : res.company record
        """
        # it may not affected because of parallel company relation
        price = line.price_unit or 0.0
        quantity = line.product_id and line.uom_id._compute_quantity(line.product_qty, line.product_id.uom_id) or line.product_qty
        price = line.product_id and line.uom_id._compute_price(price, line.product_id.uom_id) or price
        product_no_variant_attribute_value_ids = line.product_no_variant_attribute_value_ids
        return {
            'name': line.name,
            'product_uom_qty': quantity,
            'product_id': line.product_id and line.product_id.id or False,
            'product_uom_id': line.product_id and line.product_id.uom_id.id or line.uom_id.id,
            'price_unit': price,
            'discount': line.discount or 0.0,
            'company_id': company.id,
            'display_type': line.display_type,
            'sequence': line.sequence,
            'product_no_variant_attribute_value_ids': [Command.set(product_no_variant_attribute_value_ids.ids)],
            'auto_purchase_order_line_id': [Command.link(line.id)],
        }

    def _set_pcavs_from_order(self, so_lines):
        pass
