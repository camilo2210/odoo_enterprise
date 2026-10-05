# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, Command
from odoo.tools import frozendict


class PosOrder(models.Model):
    _inherit = 'pos.order'

    planning_slot_id = fields.Many2one(
        'planning.slot',
        string="Planning Slot",
        readonly=True,
        index='btree_not_null'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Sale Order",
        readonly=True,
        related='planning_slot_id.sale_order_id'
    )

    def _generate_pos_order_invoice(self):
        if self.payment_ids.payment_method_id.filtered(lambda pm: pm.type == 'resource'):
            # In case of resource-linked payment methods, the invoice is generated in the SO
            # so we don't want to generate it on the order.
            raise UserError(self.env._('The invoice for this order will be generated in the related Sales Order, because you used a payment method linked to a resource.'))
        return super()._generate_pos_order_invoice()

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        if self.sale_order_id:
            config_name = self.config_id.name
            resource_name = self.planning_slot_id.resource_ids[0].display_name
            date_order_formatted = self.create_date.strftime("%Y-%m-%d %H:%M:%S")
            self.env['sale.order.line'].sudo().with_context(sale_no_log_for_new_lines=True).create({
                "order_id": self.sale_order_id.id,
                "display_type": "line_section",
                "name": f"POS Order {self.name} - {date_order_formatted} - {config_name} - {resource_name}",
            })

            tax_aggregation = self._get_tax_aggregation()
            for tax_info in tax_aggregation:
                tax_ids = tax_info['tax_ids']
                account_id = tax_info['account_id']
                product = self.env['product.product']._get_pos_product_for_account(account_id)
                if not product:
                    continue
                self.env['sale.order.line'].sudo().create({
                    "order_id": self.sale_order_id.id,
                    "product_id": product.id,
                    "tax_ids": [Command.set(tax_ids.ids)],
                    "price_unit": tax_info['price_unit'],
                    "product_uom_qty": 1,
                    "resource_id": self.planning_slot_id.resource_ids[0].id,
                })
            if not self.currency_id.is_zero(self.amount_return):
                product = self.env['product.product']._get_pos_product_for_account(self.env['account.account'])
                self.env['sale.order.line'].sudo().create({
                    "order_id": self.sale_order_id.id,
                    "product_id": product.id,
                    "tax_ids": [],
                    "price_unit": self.amount_return,
                    "product_uom_qty": 1,
                    "resource_id": self.planning_slot_id.resource_ids[0].id,
                })
        return res

    def _get_tax_aggregation(self):
        def _grouping_function(base_line):
            return frozendict({
                'account_id': base_line['account_id'],
                'tax_ids': base_line['tax_ids'],
            })
        AccountTax = self.env['account.tax']
        base_lines = self.lines._prepare_base_lines_for_taxes_computation()
        AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        AccountTax._add_accounting_data_in_base_lines_tax_details(base_lines, self.company_id)
        return AccountTax._reduce_base_lines_with_grouping_function(
            base_lines,
            grouping_function=_grouping_function,
        )

    def _update_lines(self, order, pos_order, fields=[]):
        super()._update_lines(order, pos_order, fields=fields)
        if 'payment_ids' in fields and pos_order.payment_ids.payment_method_id.filtered(lambda pm: pm.type == 'resource'):
            # In case of resource-linked payment methods, the invoice is generated in the SO
            # so we don't want to generate it on the order AND there should be max 1 payment line.
            if order.get('to_invoice', pos_order.to_invoice):
                raise UserError(self.env._('You cannot set the order to be invoiced because you used a payment method linked to a resource. The invoice will be generated in the related Sales Order.'))
            if len(pos_order.payment_ids) > 1:
                raise UserError(self.env._('You cannot use more than one payment method when one of them is linked to a resource'))
