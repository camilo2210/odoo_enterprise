# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_br_cfop = fields.Char(
        "CFOP",
        compute="_compute_l10n_br_cfop",
        help="Brazil: CFOP returned from the tax calculation that will be used for submitting your electronic invoice per line. This is computed based on the Operation Type, product, contact and company configuration.",
    )
    l10n_br_tax_details = fields.Text(
        string="Tax Details",
        compute="_compute_l10n_br_tax_details",
        help="Brazil: Display the tax breakdown from the calculation."
    )
    l10n_br_cbs_ibs_deduction = fields.Monetary(
        string='CBS/IBS Credit',
        currency_field='currency_id',
        help='Brazil: Deduction value to reduce the CBS/IBS taxable base in outbound invoices for certain operations.',
    )

    # Add a compute to change the default.
    l10n_br_goods_operation_type_id = fields.Many2one(
        compute='_compute_l10n_br_goods_operation_type_id',
        store=True,
        readonly=False,
    )

    def _compute_l10n_br_cfop(self):
        for move, lines in self.grouped("move_id").items():
            tax_calculation_response = move.l10n_br_edi_avatax_data or {}
            aml_id_to_cfop = {line["lineCode"]: line["cfop"] for line in tax_calculation_response.get("lines", [])}

            for line in lines:
                line.l10n_br_cfop = aml_id_to_cfop.get(line.id)

    @api.depends('move_id.l10n_br_edi_avatax_data')
    def _compute_l10n_br_tax_details(self):
        br_lines = self.filtered(lambda line: line.move_id.l10n_br_is_avatax)
        line_tax_details_str = self.env['account.move']._l10n_br_get_line_tax_details_str(br_lines.grouped("move_id"))
        for line in self:
            line.l10n_br_tax_details = line_tax_details_str.get(line.id, "")

    @api.depends('product_id')
    def _compute_l10n_br_goods_operation_type_id(self):
        for line in self:
            move_id = line.move_id

            if move_id.is_sale_document() and (operation_type := line.product_id.l10n_br_operation_type_sales_id) or \
               move_id.is_purchase_document() and (operation_type := line.product_id.l10n_br_operation_type_purchases_id):
                line.l10n_br_goods_operation_type_id = operation_type
