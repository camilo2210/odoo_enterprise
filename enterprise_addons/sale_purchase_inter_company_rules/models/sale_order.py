from collections import defaultdict

from odoo import Command, SUPERUSER_ID, _, api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    auto_generated = fields.Boolean(string='Auto Generated Sales Order', copy=False)
    auto_purchase_order_id = fields.Many2one('purchase.order', string='Source Purchase Order', readonly=True, copy=False)

    def write(self, vals):
        new_order_lines = False
        if not self.env.context.get('skip_intercompany_sync'):
            existing_order_lines = self.order_line
        res = super().write(vals)
        if not self.env.context.get('skip_intercompany_sync'):
            new_order_lines = self.order_line - existing_order_lines
        if new_order_lines:
            data = self.env['purchase.order'].sudo()._read_group([('auto_sale_order_id', 'in', new_order_lines.order_id.ids)], ['auto_sale_order_id', 'id'])
            so_id_to_po = {so.id: po for so, po in data}
            for so in new_order_lines.order_id:
                if so.auto_purchase_order_id:
                    so_id_to_po[so.id] = so.sudo().auto_purchase_order_id
            if so_id_to_po:
                additions_to_log = defaultdict(lambda: self.env['sale.order.line'])  # 1 message per po
                for order_line in new_order_lines:
                    if po := so_id_to_po.get(order_line.order_id.id):
                        additions_to_log[po] |= order_line
                if additions_to_log:
                    for po, lines in additions_to_log.items():
                        existing_pols = po.order_line
                        company_rec = self.env['res.company']._find_company_from_partner(lines.order_id.partner_id.id)  # should only be 1 PO per SO
                        pol_vals = [Command.create(self.env['sale.order']._prepare_purchase_order_line_data(line, line.order_id.date_order, company_rec)) for line in lines]
                        po.sudo().with_company(po.company_id).with_context(skip_intercompany_sync=True).write({'order_line': pol_vals})
                        values = {
                            'partner_id': po.user_id.partner_id,
                            'updated_so': True,
                            'lines': po.order_line - existing_pols,
                            'display_uom': self.env.user.has_group('uom.group_uom'),
                        }
                        po.message_post_with_source(
                            'sale_purchase_inter_company_rules.added_lines_interco_so_po',
                            render_values=values,
                            partner_ids=po.user_id.partner_id.ids,
                            subtype_xmlid='mail.mt_note',
                        )
        return res

    def _action_confirm(self):
        """ Generate inter company purchase order based on conditions """
        res = super()._action_confirm()
        for order in self:
            if not order.company_id: # if company_id not found, return to normal behavior
                continue
            # if company allow to create a Purchase Order from Sales Order, then do it!
            company = self.env['res.company']._find_company_from_partner(order.partner_id.id)
            if company and company.intercompany_generate_purchase_orders and not order.auto_generated:
                order.with_user(SUPERUSER_ID).with_context(default_company_id=company.id).with_company(company).inter_company_create_purchase_order(company)
        return res

    def action_cancel(self):
        res = super().action_cancel()
        data = self.env['purchase.order'].sudo()._read_group([('auto_sale_order_id', 'in', self.ids)], ['auto_sale_order_id', 'id'])
        so_id_to_pos = {so.id: po for so, po in data}
        for so in self:
            po = so.auto_purchase_order_id.sudo() or so_id_to_pos.get(so.id)
            if po:
                values = {
                    'partner_id': po.user_id.partner_id,
                    'cancelled_so': so,
                }
                po.message_post_with_source(
                    'sale_purchase_inter_company_rules.cancelled_interco_so_po',
                    render_values=values,
                    partner_ids=po.user_id.partner_id.ids,
                    subtype_xmlid='mail.mt_note',
                )
        return res

    def inter_company_create_purchase_order(self, company):
        """ Create a Purchase Order from the current SO (self)
            Note : In this method, reading the current SO is done as sudo, and the creation of the derived
            PO as intercompany_user, minimizing the access right required for the trigger user
            :param company : the company of the created PO
            :rtype company : res.company record
        """
        for rec in self:
            if not company or not rec.company_id.partner_id:
                continue

            company_partner = rec._get_purchase_order_partner(SUPERUSER_ID)
            # create the PO and generate its lines from the SO
            # read it as sudo, because inter-compagny user can not have the access right on PO
            po_vals = rec.sudo()._prepare_purchase_order_data(company, company_partner, rec.partner_shipping_id)
            for line in rec.order_line.sudo():
                po_vals['order_line'] += [(0, 0, rec._prepare_purchase_order_line_data(line, rec.date_order, company))]
            purchase_order = self.env['purchase.order'].create(po_vals)
            msg = _("Automatically generated from %(origin)s of company %(company)s.", origin=self.name, company=rec.company_id.name)
            purchase_order.message_post(body=msg)

            # write customer reference field on SO
            if not rec.client_order_ref:
                rec.client_order_ref = purchase_order.name

            # auto-validate the purchase order if needed
            if company.intercompany_document_state == 'posted':
                purchase_order.with_user(SUPERUSER_ID).button_confirm()

    def _get_purchase_order_partner(self, user=False):
        self.ensure_one()
        return self.company_id.partner_id.with_user(user)

    def _prepare_purchase_order_data(self, company, company_partner, direct_delivery_address):
        """ Generate purchase order values, from the SO (self)
            :param company_partner : the partner representing the company of the SO
            :rtype company_partner : res.partner record
            :param company : the company in which the PO line will be created
            :rtype company : res.company record
        """
        self.ensure_one()

        return {
            'origin': self.name,
            'partner_id': company_partner.id,
            'user_id': SUPERUSER_ID,
            'date_order': self.date_order,
            'company_id': company.id,
            'fiscal_position_id': self.env['account.fiscal.position']._get_fiscal_position(company_partner).id,
            'payment_term_id': company_partner.property_supplier_payment_term_id.id,
            'auto_generated': True,
            'auto_sale_order_id': self.id,
            'partner_ref': self.name,
            'currency_id': self.currency_id.id,
            'order_line': [],
        }

    @api.model
    def _prepare_purchase_order_line_data(self, so_line, date_order, company):
        """ Generate purchase order line values, from the SO line
            :param so_line : origin SO line
            :rtype so_line : sale.order.line record
            :param date_order : the date of the orgin SO
            :param company : the company in which the PO line will be created
            :rtype company : res.company record
        """
        # price on PO so_line should be so_line - discount
        price = so_line.price_unit or 0.0
        quantity = so_line.product_id and so_line.product_uom_id._compute_quantity(so_line.product_uom_qty, so_line.product_id.uom_id) or so_line.product_uom_qty
        price = so_line.product_id and so_line.product_uom_id._compute_price(price, so_line.product_id.uom_id) or price
        return {
            'name': so_line.name,
            'product_qty': quantity,
            'product_id': so_line.product_id and so_line.product_id.id or False,
            'uom_id': so_line.product_id and so_line.product_id.uom_id.id or so_line.product_uom_id.id,
            'price_unit': price or 0.0,
            'discount': so_line.discount or 0.0,
            'company_id': company.id,
            'date_planned': so_line.order_id.commitment_date or so_line.order_id.expected_date or date_order,
            'display_type': so_line.display_type,
            'sequence': so_line.sequence,
            'auto_sale_order_line_id': so_line.id,
        }
