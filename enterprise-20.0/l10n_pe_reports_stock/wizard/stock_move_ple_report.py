from collections import defaultdict
import csv
from io import StringIO
import re

from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes, float_repr


class L10n_PeStockPleWizard(models.TransientModel):
    _name = 'l10n_pe.stock.ple.wizard'
    _description = 'Wizard to generate Stock Move PLE reports for PE'

    @api.model
    def default_get(self, fields_list):
        results = super().default_get(fields_list)
        if self.env.company.country_code != 'PE':
            raise UserError(self.env._('This option is only available for Peruvian companies.'))
        date_from = fields.Date.context_today(self).replace(day=1)
        results['date_from'] = date_from
        results['date_to'] = date_from + relativedelta(months=1, days=-1)
        return results

    date_from = fields.Date(
        required=True,
        help="Choose a date from to get the PLE reports at that date",
    )
    date_to = fields.Date(
        required=True,
        help="Choose a date to get the PLE reports at that date",
    )
    report_data = fields.Binary('Report file', readonly=True, attachment=False)
    report_filename = fields.Char(string='Filename', readonly=True)
    mimetype = fields.Char(string='Mimetype', readonly=True)

    def get_ple_report_12_1(self):
        return self.get_ple_report('1201')

    def get_ple_report_13_1(self):
        return self.get_ple_report('1301')

    def get_ple_report(self, report_number):
        data = self._get_ple_report_content(report_number)
        has_data = "1" if data else "0"
        filename = "LE%s%s%02d00%s00001%s11.txt" % (
            self.env.company.vat, self.date_from.year, self.date_from.month, report_number, has_data)
        self.write({
            'report_data': BinaryBytes(data.encode()),
            'report_filename': filename,
            'mimetype': 'application/txt',
        })
        return {
            'type': 'ir.actions.act_url',
            'url':  '/web/content/?' + url_encode({
                'model': self._name,
                'id': self.id,
                'filename_field': 'report_filename',
                'field': 'report_data',
                'download': 'true'
            }),
            'target': 'new'
        }

    @api.model
    def _get_serie_folio(self, number):
        values = {"serie": "", "folio": ""}
        number_matchs = list(re.finditer("\\d+", number or ""))
        if number_matchs:
            last_number_match = number_matchs[-1]
            values["serie"] = number[: last_number_match.start()].replace("-", "") or ""
            values["folio"] = last_number_match.group() or ""
        return values

    @api.model
    def _get_stock_valuation(self, category_id):
        cost_method = self.env['product.category'].browse(category_id).property_cost_method
        return {'average': '1', 'fifo': '2', 'standard': '3'}.get(cost_method, '')

    @api.model
    def _product_row_values(self, product):
        product_tmpl = product.product_tmpl_id
        return {
            'catalogue': '1',
            'type_of_existence': (product_tmpl.l10n_pe_type_of_existence or '99').zfill(2),
            'default_code': re.sub(r"[_\-/']", '', product.default_code or '')[:24],
            'catalogue_used': '1',
            'unspsc': product_tmpl.unspsc_code_id.code or '',
        }

    @api.model
    def _product_name(self, product):
        return (product.name or '').replace('"', "'")[:80]

    def _get_ple_report_content(self, report):
        data = []
        period = '%s%s00' % (self.date_from.year, str(self.date_from.month).zfill(2))
        moves = self._get_ple_reports_data()
        data_per_products = {}
        delivery_number_installed = 'l10n_latam_document_number' in self.env['stock.picking']._fields

        adjustments_by_move = self._get_move_valuation_adjustments(moves)
        for move in moves:
            product = move.product_id
            product_tmpl = product.product_tmpl_id
            # Sort by id to consistently pick the first-created invoice,
            # matching 18.0's SQL behavior (ORDER BY am.id / am_p.id NULLS LAST).
            # account.move default _order is 'date desc, id desc' so [:1] alone
            # would incorrectly pick the latest invoice.
            invoice = move.sale_line_id.invoice_lines.move_id.sorted('id')[:1]
            bill = move.purchase_line_id.invoice_lines.move_id.sorted('id')[:1]

            picking_name = move.picking_id.name or ''
            delivery_number = (
                move.picking_id.l10n_latam_document_number
                if delivery_number_installed and move.picking_id.l10n_latam_document_number
                else ''
            )
            serie_folio = self._get_serie_folio(
                delivery_number or invoice.name or bill.name or picking_name or ''
            )
            date = (invoice.invoice_date or bill.invoice_date or move.date)
            date = date.strftime('%d/%m/%Y') if date else ''

            document_type_code = (
                (invoice.l10n_latam_document_type_id or bill.l10n_latam_document_type_id).code or '00'
            )
            operation_type = (move.picking_id.l10n_pe_operation_type or '99').zfill(2)
            if not move.picking_id.l10n_pe_operation_type and move.picking_type_id.code == 'mrp_operation':
                operation_type = '19' if move.is_in else '27'
            if delivery_number or (
                operation_type in ('01', '02', '03', '04', '05', '06') and document_type_code == '00'
            ):
                document_type_code = '09'

            # Opening balance line for first occurrence of each product
            if product.id not in data_per_products:
                valuation_data = self._append_valuation_line(move, period, report)
                data_per_products[product.id] = [
                    valuation_data.get('remaining', 0),
                    valuation_data.get('value', 0),
                ]
                if valuation_data:
                    data.append(valuation_data)

            # Compute quantity and value for this move
            quantity = move._get_valued_qty() if move.is_in else -move._get_valued_qty()
            if report == '1201' and not quantity:
                continue
            if not quantity:
                operation_type = '99'

            values = {
                'period': period,
                'cuo': str(move.id).zfill(6),
                'number': 'M1',
                'establishment': move.warehouse_id.l10n_pe_anexo_establishment_code or '0000',
                **self._product_row_values(product),
                'date': date,
                'document_type': document_type_code,
                'serie': serie_folio['serie'].replace(' ', '').replace('/', '') or '0',
                'folio': serie_folio['folio'].replace(' ', '') or '0',
                'operation_type': operation_type,
                'product': self._product_name(product),
                'uom': move.uom_id.l10n_pe_edi_measure_unit_code,
            }
            if report == '1201':
                values.update({
                    'qty_in': quantity if quantity > 0 else 0,
                    'qty_out': quantity if quantity <= 0 else 0,
                    'state': '1',
                })
                data.append(values)
                continue

            adjustments = adjustments_by_move.get(move.id, [])
            total_cost = (move.value if move.is_in else -abs(move.value)) - sum(a['value'] for a in adjustments)
            balance = data_per_products[product.id]
            balance[0] += quantity
            balance[1] += total_cost
            values.update({
                'valuation': self._get_stock_valuation(product_tmpl.categ_id.id),
                **self._valuation_columns(quantity, total_cost, balance[0], balance[1]),
                'state': '1',
            })
            data.append(values)

            # Each valuation adjustment (e.g. a landed cost) gets its own line.
            for adjustment in adjustments:
                balance[1] += adjustment['value']
                data.append(self._build_adjustment_line(move, product, period, adjustment, balance))
        data.extend(self._append_historic_valuation_lines(list(data_per_products), period, report))
        if not data:
            return ''

        float_fields = (
            "qty_in", "cost_in", "value_in",
            "qty_out", "cost_out", "value_out",
            "remaining", "unit_cost_final", "value",
        )
        for element in data:
            for field in float_fields:
                if field in element:
                    element[field] = float_repr(round(float(element[field] or 0.0), 2), precision_digits=2)

        output = StringIO()
        writer = csv.DictWriter(output, delimiter="|", skipinitialspace=True, lineterminator='\n', fieldnames=[*data[0], object()])
        writer.writerows(data)
        txt_result = output.getvalue()
        return txt_result

    @api.model
    def _valuation_columns(self, quantity, value, running_qty, running_value, is_balance=False):
        """Return the in/out and running balance columns of a valued line."""
        unit_cost = abs(value / quantity) if quantity else 0
        return {
            'qty_in': quantity if quantity > 0 else 0,
            'cost_in': unit_cost if (quantity > 0 or is_balance) else 0,
            'value_in': value if value > 0 else 0,
            'qty_out': quantity if quantity < 0 else 0,
            'cost_out': unit_cost if quantity < 0 else 0,
            'value_out': value if value <= 0 else 0,
            'remaining': running_qty,
            'unit_cost_final': abs(running_value / (running_qty or 1)),
            'value': running_value,
        }

    def _append_valuation_line(self, move, period, report):
        product = move.product_id
        domain = [
            ('company_id', '=', self.env.company.id),
            ('product_id', '=', product.id),
            ('product_id.is_storable', '=', True),
            ('state', '=', 'done'),
            ('date', '<', self.date_from),
        ]
        moves_in = self.env['stock.move']._read_group(
            domain + [('is_in', '=', True)],
            ['uom_id'],
            ['value:sum', 'quantity:sum'],
        )
        moves_out = self.env['stock.move']._read_group(
            domain + [('is_out', '=', True)],
            ['uom_id'],
            ['value:sum', 'quantity:sum'],
        )

        value_in = sum(value for __, value, __ in moves_in)
        qty_in = sum(uom._compute_quantity(qty, product.uom_id) for uom, __, qty in moves_in)
        value_out = sum(value for __, value, __ in moves_out)
        qty_out = sum(uom._compute_quantity(qty, product.uom_id) for uom, __, qty in moves_out)

        quantity = qty_in - qty_out
        value = value_in + value_out
        if not quantity:
            return {}

        values = {
            'period': period,
            'cuo': f'{product.id}A1'.zfill(6),
            'number': 'A1',
            'establishment': move.warehouse_id.l10n_pe_anexo_establishment_code or '0000',
            **self._product_row_values(product),
            'type_of_existence': '99',
            'date': self.date_from.strftime('%d/%m/%Y'),
            'document_type': '00',
            'serie': '0',
            'folio': '0',
            'operation_type': '16',
            'product': self._product_name(product),
            'uom': product.uom_id.l10n_pe_edi_measure_unit_code,
        }
        if report == '1201':
            values.update({
                'qty_in': quantity if quantity > 0 else 0,
                'qty_out': 0,
                'state': '1',
            })
            return values

        values.update({
            'valuation': self._get_stock_valuation(product.categ_id.id),
            **self._valuation_columns(quantity, value, quantity, value, is_balance=True),
            'state': '1',
        })
        return values

    def _append_historic_valuation_lines(self, products, period, report):
        domain = [
            ('company_id', '=', self.env.company.id),
            ('product_id.is_storable', '=', True),
            ('state', '=', 'done'),
            ('date', '<', self.date_from),
        ]
        if products:
            domain.append(('product_id', 'not in', products))
        moves_in = self.env['stock.move']._read_group(
            domain + [('is_in', '=', True)],
            ['product_id', 'uom_id'],
            ['value:sum', 'quantity:sum'],
        )
        moves_out = self.env['stock.move']._read_group(
            domain + [('is_out', '=', True)],
            ['product_id', 'uom_id'],
            ['value:sum', 'quantity:sum'],
        )

        balances = defaultdict(lambda: {'quantity': 0, 'value': 0})
        for product, uom, value, qty in moves_in:
            balances[product]['quantity'] += uom._compute_quantity(qty, product.uom_id)
            balances[product]['value'] += value
        for product, uom, value, qty in moves_out:
            balances[product]['quantity'] -= uom._compute_quantity(qty, product.uom_id)
            balances[product]['value'] += value

        data = []
        for product, vals in balances.items():
            quantity = vals['quantity']
            if not quantity:
                continue
            value = vals['value']
            values = {
                'period': period,
                'cuo': f'{product.id}A1'.zfill(6),
                'number': 'A1',
                'establishment': '0000',
                **self._product_row_values(product),
                'type_of_existence': '99',
                'date': self.date_from.strftime('%d/%m/%Y'),
                'document_type': '00',
                'serie': '0',
                'folio': '0',
                'operation_type': '16',
                'product': self._product_name(product),
                'uom': product.uom_id.l10n_pe_edi_measure_unit_code,
            }
            if report == '1201':
                values.update({
                    'qty_in': quantity,
                    'qty_out': 0,
                    'state': '1',
                })
                data.append(values)
                continue

            values.update({
                'valuation': self._get_stock_valuation(product.categ_id.id),
                **self._valuation_columns(quantity, value, quantity, value, is_balance=True),
                'state': '1',
            })
            data.append(values)
        return data

    def _get_ple_reports_data(self):
        domain = [
            ('state', '=', 'done'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.env.company.id),
            ('product_id.is_storable', '=', True),
            '|',
            ('location_id.usage', 'in', ('supplier', 'customer', 'inventory', 'production')),
            ('location_dest_id.usage', 'in', ('supplier', 'customer', 'inventory', 'production')),
        ]
        return self.env['stock.move'].search(domain, order="product_id, date, id")

    def _get_move_valuation_adjustments(self, moves):
        """Return a dict mapping a move id to its valuation adjustments.

        Each adjustment is a dict with the 'cuo', 'value', 'operation_type',
        'date', 'document_type', 'serie' and 'folio'.
        """
        return {}

    @api.model
    def _build_adjustment_line(self, move, product, period, adjustment, balance):
        value = adjustment['value']
        running_qty, running_value = balance
        return {
            'period': period,
            'cuo': adjustment['cuo'],
            'number': 'M1',
            'establishment': move.warehouse_id.l10n_pe_anexo_establishment_code or '0000',
            **self._product_row_values(product),
            'date': adjustment['date'],
            'document_type': adjustment.get('document_type', '00'),
            'serie': adjustment.get('serie') or '0',
            'folio': adjustment.get('folio') or '0',
            'operation_type': adjustment['operation_type'],
            'product': self._product_name(product),
            'uom': move.uom_id.l10n_pe_edi_measure_unit_code,
            'valuation': self._get_stock_valuation(product.categ_id.id),
            'qty_in': 0,
            'cost_in': value if value > 0 else 0,
            'value_in': value if value > 0 else 0,
            'qty_out': 0,
            'cost_out': abs(value) if value < 0 else 0,
            'value_out': abs(value) if value < 0 else 0,
            'remaining': running_qty,
            'unit_cost_final': abs(running_value / (running_qty or 1)),
            'value': running_value,
            'state': '1',
        }
