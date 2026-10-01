from odoo import api, models


class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', 'account.external.tax.mixin', 'account.avatax.unique.code']

    @api.depends('config_id.module_pos_avatax')
    def _compute_is_avatax(self):
        """ account.external.tax.mixin override. Only consider the config boolean, not the fiscal position. """
        for order in self:
            order.is_avatax = order.config_id.module_pos_avatax

    def _get_and_set_external_taxes_on_eligible_records(self):
        """ account.external.tax.mixin override. """
        eligible_orders = self.filtered(lambda order: order.is_tax_computed_externally and order.state == 'draft')
        eligible_orders._set_external_taxes(eligible_orders._get_external_taxes())
        return super()._get_and_set_external_taxes_on_eligible_records()

    def _get_line_data_for_external_taxes(self):
        """ account.external.tax.mixin override. """
        AccountTax = self.env['account.tax']
        base_lines = self.lines._prepare_base_lines_for_taxes_computation()
        AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return [{
            'base_line': base_line,
            'description': base_line['record'].product_id.name,
            # account_avatax_stock reads these. POS sales are taxed from the company location, so there is no per-line
            # warehouse origin and the order-level ship to/from addresses (both the company) are used.
            'warehouse_id': False,
            'shipping_partner': self.company_id.partner_id,
        } for base_line in base_lines]

    def _get_avatax_service_params(self):
        # EXTENDS 'account.external.tax.mixin'
        res = super()._get_avatax_service_params()
        res.update({
            'is_refund': False,  # refunds in the POS are negative, so no need to invert the sign like with sale.order and account.move
            'document_type': 'SalesOrder',
            'document_date': self.date_order,
            'tax_date': self.date_order,
            'perform_address_validation': False,
        })
        return res

    def _get_avatax_ship_to_partner(self):
        """ account.external.tax.mixin override. POS sales are always taxed based on the location of the POS, not the
        customer. A branch can be created if this address is different from the main company. """
        return self.company_id.partner_id

    @api.model
    def get_order_tax_details(self, orders):
        res = self.env['pos.order'].sync_from_ui(orders)
        order_ids = self.browse([order['id'] for order in res['pos.order']])
        results = {
            **res,
            'pos.order': [],
            'pos.order.line': [],
            'account.tax': [],
            'account.tax.group': [],
        }

        for order in order_ids:
            order.button_external_tax_calculation()
            config = order.config_id
            results['account.tax'] += self.env['account.tax']._load_pos_data_read(order.lines.tax_ids, config)
            results['account.tax.group'] += self.env['account.tax.group']._load_pos_data_read(order.lines.tax_ids.tax_group_id, config)
            results['pos.order'] += self.env['pos.order']._load_pos_data_read(order, config)
            results['pos.order.line'] += self.env['pos.order.line']._load_pos_data_read(order.lines, config) if config else []

        return results
