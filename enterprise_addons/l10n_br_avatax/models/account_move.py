# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_br_shipping_state_id = fields.Many2one(
        string="Shipping State",
        comodel_name="res.country.state",
        domain=[('country_id.code', '=', 'BR')],
        help="Brazil: the state from which the products will be shipped internationally."
    )
    l10n_br_partner_country_code = fields.Char(
        string="Partner Country Code",
        related="partner_id.country_code"
    )

    def _depends_l10n_br_avatax_warnings(self):
        """account.external.tax.mixin override."""
        return super()._depends_l10n_br_avatax_warnings() + [
            "invoice_line_ids.product_id",
            "l10n_br_goods_operation_type_id",
            "invoice_line_ids.l10n_br_goods_operation_type_id",
            "partner_shipping_id",
            "incoterm_location",
            "l10n_br_shipping_state_id",
        ]

    def _get_line_data_for_external_taxes(self):
        """ Override to set the operation_type, order_number, order_item_number per line. """
        res = super()._get_line_data_for_external_taxes()
        for line in res:
            aml = line['base_line']['record']
            line['operation_type'] = aml.l10n_br_goods_operation_type_id or aml.move_id.l10n_br_goods_operation_type_id
            line['order_number'] = aml.l10n_br_order_number
            line['order_item_number'] = aml.l10n_br_item_number
        return res

    def _compute_l10n_br_is_avatax_depends(self):
        # EXTENDS account.external.tax.mixin
        return super()._compute_l10n_br_is_avatax_depends() + ["move_type"]

    def _l10n_br_is_avatax(self):
        # EXTENDS account.external.tax.mixin to restrict to sales and purchase documents
        return super()._l10n_br_is_avatax() and (self.is_sale_document() or self.is_purchase_document())

    @api.depends("l10n_br_is_avatax", "move_type", "debit_origin_id")
    def _compute_l10n_br_goods_operation_type_id(self):
        """Override."""
        move_type_to_operation_type = {
            "out_invoice": "l10n_br_avatax.operation_type_1",  # standardSales
            "out_refund": "l10n_br_avatax.operation_type_60",  # salesReturn
            "in_invoice": "l10n_br_avatax.operation_type_59",  # standardPurchase
            "in_refund": "l10n_br_avatax.operation_type_31",  # standardPurchaseReturnShippingOutbound
        }

        self.l10n_br_goods_operation_type_id = False
        for move in self.filtered("l10n_br_is_avatax"):
            if move.debit_origin_id:
                move.l10n_br_goods_operation_type_id = self.env.ref("l10n_br_avatax.operation_type_3")  # amountComplementary
            else:
                move.l10n_br_goods_operation_type_id = self.env.ref(move_type_to_operation_type.get(move.move_type), raise_if_not_found=False)

    @api.depends("l10n_latam_document_type_id")
    def _compute_l10n_br_is_service_transaction(self):
        """account.external.tax.mixin override."""
        for move in self:
            move.l10n_br_is_service_transaction = (
                move.l10n_br_is_avatax and move.l10n_latam_document_type_id == self.env.ref("l10n_br.dt_SE")
            )

    def _get_external_taxes(self):
        """ Override of account.external.tax.mixin. """
        for invoice in self.filtered('l10n_br_is_avatax'):
            # This type of transaction requires installments with a `grossValue` before subtracted taxes. Clear any
            # already existing taxes to ensure that previous tax calculations haven't altered the down payment lines.
            if invoice.l10n_br_is_service_transaction and invoice._get_l10n_br_avatax_service_params().get('installments'):
                invoice.invoice_line_ids.filtered('tax_ids').write({
                    'tax_ids': [Command.clear()],
                    'extra_tax_data': False,
                })

        return super()._get_external_taxes()

    def _l10n_br_avatax_check_missing_fields_product(self, lines):
        """account.external.tax.mixin override."""
        res = super()._l10n_br_avatax_check_missing_fields_product(lines)
        warning_fields = ["l10n_br_use_type"]

        if self.l10n_br_is_service_transaction:
            warning_fields += ["l10n_br_property_service_code_origin_id", "l10n_br_service_code_ids"]
        else:
            warning_fields += ["l10n_br_ncm_code_id", "l10n_br_sped_type", "l10n_br_source_origin"]

        # These fields can also be resolved through the operation type cascade, so warn only when the resolved
        # payload value is empty rather than the raw product field.
        resolved_field_values = {
            "l10n_br_use_type": lambda line: line["useType"],
            "l10n_br_sped_type": lambda line: line["itemDescriptor"].get("productType"),
            "l10n_br_source_origin": lambda line: line["itemDescriptor"].get("source"),
        }

        incomplete_products = self.env['product.product']
        fields = set()

        for line in lines:
            product = line['tempProduct']
            if not product:
                continue

            for field in warning_fields:
                resolver = resolved_field_values.get(field)
                value = resolver(line) if resolver else product[field]
                if not value:
                    incomplete_products |= product
                    fields.add(product._fields[field])

        if incomplete_products:
            res["invoice_products_missing_fields_warning"] = {
                "message": _(
                    "To avoid tax miscalculations make sure to set up %(fields)s on an operation type or on the following:\n%(products)s",
                    fields=[field._description_string(self.env) for field in fields],
                    products=incomplete_products.mapped("display_name"),
                ),
                "action_text": _("View products"),
                "action": incomplete_products._l10n_br_avatax_action_missing_fields(self.l10n_br_is_service_transaction),
                "level": "warning",
            }

        return res

    def _l10n_br_avatax_check_partner(self):
        """account.external.tax.mixin override."""
        res = super()._l10n_br_avatax_check_partner()
        recommended_fields = ("street_name", "street_number", "street2", "zip", "l10n_br_tax_regime", "l10n_br_taxpayer", "l10n_br_activity_sector", "state_id")
        missing_fields = [self.partner_id._fields[field] for field in recommended_fields if not self.partner_id[field]]
        if missing_fields:
            res["missing_partner_fields_warning"] = {
                "message": _(
                    "To avoid tax miscalculations make sure to set up %(fields)s on %(partner_name)s.",
                    fields=[field._description_string(self.env) for field in missing_fields],
                    partner_name=self.partner_id.display_name
                ),
                "action_text": _("View customer"),
                "action": self.partner_id._l10n_br_avatax_action_missing_fields(),
                "level": "warning",
            }

        return res

    def _l10n_br_avatax_check_missing_export_fields(self, params):
        res = {}
        if params['is_export_goods']:
            if not params['incoterm_location']:
                res['missing_incoterm_location'] = {
                    "message": _("Incoterm Location is required to calculate taxes with Avatax for export of goods."),
                    "level": "danger",
                }
            if not params['shipping_state_id']:
                res['missing_shipping_state'] = {
                    "message": _("Shipping State is required to calculate taxes with Avatax for export of goods."),
                    "level": "danger",
                }
        return res

    def _compute_l10n_br_avatax_warnings(self):
        """account.external.tax.mixin override."""
        super()._compute_l10n_br_avatax_warnings()

        for move in self:
            if not move.l10n_br_is_avatax:
                move.l10n_br_avatax_warnings = False
                continue

            move.l10n_br_avatax_warnings = {
                **(move.l10n_br_avatax_warnings or {}),
                **move._l10n_br_avatax_check_missing_export_fields(move._get_l10n_br_avatax_service_params())
            }

    def _get_l10n_br_avatax_service_params(self):
        params = super()._get_l10n_br_avatax_service_params()

        if origin := self.debit_origin_id or self.reversed_entry_id:
            params['origin_record'] = origin
            params['invoice_refs'] = {
                'invoicesRefs': [
                    {
                        'type': 'documentCode',
                        'documentCode': f'{origin._name}_{origin.id}',
                    }
                ]
            }

        payments = self.line_ids.filtered(lambda line: line.display_type == 'payment_term' and line.date_maturity)
        future_payments = payments.filtered(
            lambda line: line.date_maturity > (self.invoice_date or fields.Date.context_today(self))
        )
        if future_payments:
            params['installments'] = {
                'installmentTerms': '1' if len(payments) == 1 else '5',
                'bill': {
                    'nFat': self.name,
                    'vNet': self.amount_total,
                    'vOrig': self.amount_total,
                },
                'installment': [
                    {
                        'documentNumber': f'{index + 1:03}',
                        'date': payment.date_maturity.isoformat(),
                        'grossValue': payment.balance,
                        'netValue': payment.balance,
                    }
                    for index, payment in enumerate(payments.sorted('date_maturity'))
                ],
            }

        params.update({
            'document_date': self.invoice_date,
            'partner_shipping': self.partner_shipping_id,
            'is_export_goods': self.partner_id.country_id != self.env.ref('base.br') and self.l10n_latam_document_type_id == self.env.ref('l10n_br.dt_55'),
            'shipping_state_id': self.l10n_br_shipping_state_id,
            'incoterm_location': self.incoterm_location,
        })

        return params
