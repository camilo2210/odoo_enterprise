# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    l10n_br_tax_details = fields.Text(
        string="Tax Details",
        compute="_compute_l10n_br_tax_details",
        help="Brazil: Display the tax breakdown from the calculation."
    )

    # Add a compute to change the default.
    l10n_br_goods_operation_type_id = fields.Many2one(
        compute='_compute_l10n_br_goods_operation_type_id',
        store=True,
        readonly=False,
    )

    @api.depends('order_id.l10n_br_edi_avatax_data')
    def _compute_l10n_br_tax_details(self):
        br_lines = self.filtered(lambda line: line.order_id.l10n_br_is_avatax)
        line_tax_details_str = self.env['sale.order']._l10n_br_get_line_tax_details_str(br_lines.grouped("order_id"))
        for line in self:
            line.l10n_br_tax_details = line_tax_details_str.get(line.id, "")

    @api.depends('product_id')
    def _compute_l10n_br_goods_operation_type_id(self):
        for line in self:
            line.l10n_br_goods_operation_type_id = line.product_id.l10n_br_operation_type_sales_id
