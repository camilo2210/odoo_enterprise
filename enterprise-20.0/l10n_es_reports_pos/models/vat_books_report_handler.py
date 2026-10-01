# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

from odoo.addons.l10n_es_reports.models.vat_books_report_handler import INCOME_FIELDS


class L10n_EsVATBooksReportHandler(models.AbstractModel):
    _inherit = 'l10n_es.vat.books.report.handler'

    def _l10n_es_libros_get_content_domain(self, report, options):
        domain = super()._l10n_es_libros_get_content_domain(report, options)
        if self.env.company._l10n_es_get_pos_edi_mode():
            # Exclude the aggregate POS session moves
            domain += [('move_id.pos_session_ids', '=', False)]
        return domain

    def _l10n_es_libros_get_common_line_vals(self, line, tax):
        line_vals = super()._l10n_es_libros_get_common_line_vals(line, tax)
        if line.move_id.pos_session_ids:
            # The aggregate POS session move is a summary of simplified invoices.
            line_vals['invoice_type'] = 'R5' if line.is_refund else 'F4'
        return line_vals

    def _l10n_es_libros_is_income_line(self, line):
        return (
            line.move_id.move_type == 'entry'
            and bool(line.move_id.sudo().pos_session_ids)
        ) or super()._l10n_es_libros_is_income_line(line)

    def _l10n_es_libros_create_income_line_vals(self, line, tax):
        line_vals = super()._l10n_es_libros_create_income_line_vals(line, tax)
        if session := line.move_id.sudo().pos_session_ids[:1]:
            if line.is_refund:
                line_vals['invoice_number'] = session.name
            elif active_orders := session.order_ids.filtered(lambda o: not o.refunded_order_id).sorted('id'):
                line_vals['invoice_number'] = active_orders[0].name
                line_vals['invoice_final_number'] = active_orders[-1].name
        return line_vals

    def _l10n_es_libros_get_pos_order_invoice_number(self, pos_order):
        pos_order.ensure_one()
        pos_edi_mode = pos_order.company_id._l10n_es_get_pos_edi_mode()
        if pos_edi_mode == 'verifactu':
            return pos_order.name
        return pos_order.pos_reference

    def _l10n_es_libros_get_pos_order_domain(self, options):
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        return [
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
            ('state', 'in', ['paid', 'done']),
            ('company_id', 'in', self.env.companies.ids),
            '|', ('account_move', '=', False), ('account_move.pos_session_ids', '!=', False),
        ]

    def _l10n_es_libros_get_pos_order_sheet_line_vals(self, pos_order):
        """Build VAT book line_vals for a single POS order (EDI mode)."""
        pos_order.ensure_one()
        company = pos_order.company_id
        partner = pos_order.partner_id
        exempt_reason = pos_order.lines.tax_ids.filtered(lambda t: t.l10n_es_exempt_reason == 'E2')
        invoice_type = 'F2' if pos_order.amount_total >= 0 else 'R5'
        operation_code = '02' if exempt_reason else '01'
        amount = 0
        common_line_vals = self._l10n_es_fill_common_line_vals(
            company,
            partner,
            pos_order.date_order,
            pos_order.date_order,
            invoice_type,
            operation_code,
            amount,
        )

        AccountTax = self.env['account.tax']
        sujeto_tax_types = AccountTax._l10n_es_get_sujeto_tax_types()

        base_lines = pos_order.lines._prepare_base_lines_for_taxes_computation()
        AccountTax._add_tax_details_in_base_lines(base_lines, company)
        AccountTax._round_base_lines_tax_details(base_lines, company)

        def grouping_function(base_line, tax_data):
            if not tax_data or tax_data['is_reverse_charge']:
                return None
            tax = tax_data['tax']
            if tax.amount == -100 or tax.l10n_es_type in ('ignore', 'retencion'):
                return None
            recargo_taxes = base_line['tax_ids'].filtered(lambda t: t.l10n_es_type == 'recargo')
            return {
                'amount': tax.amount,
                'recargo_taxes': recargo_taxes,
                'l10n_es_bien_inversion': tax.l10n_es_bien_inversion,
                'l10n_es_exempt_reason': tax.l10n_es_exempt_reason if tax.l10n_es_type == 'exento' else False,
                'l10n_es_type': tax.l10n_es_type,
            }

        aggregated_values = AccountTax._aggregate_base_lines_tax_details(base_lines, grouping_function)
        tax_details = AccountTax._aggregate_base_lines_aggregated_values(aggregated_values)

        tax_detail_items = [(k, v) for k, v in tax_details.items() if k]
        # Map each main tax key to its paired recargo key (matched by recargo tax amount)
        recargo_keys = [k for k in tax_details if k and k['l10n_es_type'] == 'recargo']
        recargo_by_main_key = {}
        for key, _detail in tax_detail_items:
            if key['l10n_es_type'] == 'recargo':
                continue
            recargo_taxes = key['recargo_taxes']
            if recargo_taxes:
                matched = next(
                    (k for k in recargo_keys if any(t.amount == k['amount'] for t in recargo_taxes)),
                    None,
                )
                recargo_by_main_key[key] = matched

        # POS base lines normalise refund quantities to positive amounts
        sign = 1 if pos_order.amount_total >= 0 else -1

        sheet_line_vals = []
        for key, detail in tax_detail_items:
            tax_type = key['l10n_es_type']
            if tax_type == 'recargo':
                continue

            tax_percentage = key['amount']
            base_amount = sign * detail['base_amount']
            tax_amount = sign * (detail['tax_amount'] or 0)

            calificacion_operacion = None
            recargo_percentage = None
            recargo_amount = None

            if tax_type in sujeto_tax_types:
                calificacion_operacion = 'S2' if tax_type == 'sujeto_isp' else 'S1'
                recargo_key = recargo_by_main_key.get(key)
                if recargo_key:
                    recargo_detail = tax_details[recargo_key]
                    recargo_percentage = recargo_key['amount']
                    recargo_amount = sign * (recargo_detail['tax_amount'] or 0)
            elif tax_type in ('no_sujeto', 'no_sujeto_loc'):
                calificacion_operacion = 'N2' if tax_type == 'no_sujeto_loc' else 'N1'

            line_vals = {field: '' for field in INCOME_FIELDS}
            line_vals.update(common_line_vals)
            invoice_number = self._l10n_es_libros_get_pos_order_invoice_number(pos_order)
            line_vals.update({
                'income_concept': 'I01',
                'income_computable': base_amount,
                'invoice_number': invoice_number,
                'operation_qualification': calificacion_operacion,
                'operation_exempt': key.get('l10n_es_exempt_reason') if tax_type == 'exento' else '',
            })
            if calificacion_operacion == 'S2':
                tax_percentage = 0
            line_vals.update({
                'total_amount': base_amount + (tax_amount or 0) + (recargo_amount or 0),
                'base_amount': base_amount,
                'income_computable': base_amount,
                'tax_rate': tax_percentage,
                'taxed_amount': tax_amount,
                'surcharge_type': recargo_percentage or 0,
                'surcharge_fee': recargo_amount or 0,
                'withholding_type': 0,
                'withholding_amount': 0,
            })
            sheet_line_vals.append(line_vals)

        return sheet_line_vals

    def _l10n_es_libros_iter_pos_order_batches(self, options):
        batch_size = 10000
        batch_offset = 0
        domain = self._l10n_es_libros_get_pos_order_domain(options)
        while pos_order_ids := self.env['pos.order'].sudo().search(domain, offset=batch_offset, limit=batch_size, order='id').ids:
            yield pos_order_ids
            self.env['pos.order'].invalidate_model()
            self.env['pos.order.line'].invalidate_model()
            self.env['res.partner'].invalidate_model()
            if len(pos_order_ids) < batch_size:
                break
            batch_offset += batch_size

    def _l10n_es_libros_fill_content(self, sheet_income, sheet_expense, report, options):
        row_trackers = super()._l10n_es_libros_fill_content(sheet_income, sheet_expense, report, options)
        if self.env.company._l10n_es_get_pos_edi_mode():
            for pos_orders_ids in self._l10n_es_libros_iter_pos_order_batches(options):
                for pos_order in self.env['pos.order'].sudo().browse(pos_orders_ids):
                    for line_vals in self._l10n_es_libros_get_pos_order_sheet_line_vals(pos_order):
                        row_trackers['inc'] = self._l10n_es_libros_write_sheet_line_vals(
                            sheet_income, row_trackers['inc'], line_vals, INCOME_FIELDS, options)
        return row_trackers
