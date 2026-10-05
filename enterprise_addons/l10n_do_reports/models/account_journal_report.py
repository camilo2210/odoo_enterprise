# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import SQL, float_repr

# Tax grids (account.account.tag names) feeding the 606 amount columns
ITBIS_PURCHASE_TAGS = ('tax.paid.purchase', 'tax.paid.service', 'tax.paid.imports', 'tax.cost.purchase')
ITBIS_COST_TAGS = ('tax.cost.purchase',)
ITBIS_WITHHELD_TAGS = ('A.50',)
ISR_WITHHELD_TAGS = ('tax.isr.purchase',)


class JournalReportCustomHandler(models.AbstractModel):
    _inherit = 'account.journal.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        if self.env.company.account_fiscal_country_id.code != 'DO':
            return

        options['buttons'].append({
            'name': self.env._('Generate 606 DGII'),
            'sequence': 80,
            'action': 'export_file',
            'action_param': 'l10n_do_export_606_to_txt',
            'file_export_type': self.env._('TXT'),
        })

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        super()._customize_warnings(report, options, all_column_groups_expression_totals, warnings)
        # The 606 is filed per calendar month: warn (without blocking the report,
        # which remains usable over any range) when the selected period is not one.
        # Custom dates exactly spanning a calendar month are normalized to the
        # 'month' period type by the date filter, so they don't raise the warning.
        if (
            self.env.company.account_fiscal_country_id.code == 'DO'
            and options['date']['period_type'] != 'month'
        ):
            warnings['l10n_do_reports.warning_606_period_not_month'] = {'alert_type': 'warning'}

    def l10n_do_export_606_to_txt(self, options):
        """ Exports the purchases of the period as the pipe-delimited TXT file
        expected by the DGII Format 606, ready to be uploaded as-is.

        The 606 is filed per company: each DO company keeps its own currency
        and is reported under its own RNC, so the export is scoped to the
        active company only, even when several are selected in the report.
        """
        company = self.env.company
        moves = self.env['account.move'].search([
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', '=', 'posted'),
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
            ('company_id', '=', company.id),
        ], order='invoice_date, name')

        rnc = self._l10n_do_format_rnc(company.vat)
        period = options['date']['date_to'][:7].replace('-', '')
        rows = self._l10n_do_get_606_rows(moves)
        buffer = io.StringIO()
        csv.writer(buffer, delimiter='|', lineterminator='\r\n').writerows(
            [['606', rnc, period, str(len(rows))], *rows],
        )
        # No trailing CRLF after the last line
        content = buffer.getvalue().rstrip('\r\n')
        return {
            'file_name': f"DGII_F_606_{rnc}_{period}.TXT",
            'file_content': content.encode(),
            'file_type': 'txt',
        }

    @api.model
    def _l10n_do_get_606_rows(self, moves):
        """ Build one row per move (in the given order), in the exact 23-field
        order expected by the DGII Format 606 submission TXT.
        """
        amounts = self._l10n_do_get_606_amounts(moves)

        def amt(amount, factor):
            return move.company_id.currency_id.round(factor * (amount or 0.0))

        errors = []
        rows = []
        for move in moves:
            partner = move.partner_id
            if partner.country_code != 'DO':
                # Purchases from foreign suppliers are not reported on the 606
                continue
            # Individuals are identified by their Cédula, the others by their RNC (the DO tax ID)
            cedula = partner._get_additional_identifier('DO_CEDULA')
            id_type = '2' if cedula else '1'
            identifier = cedula or partner.vat
            if not identifier:
                errors.append(self.env._("%s: the vendor has no RNC/Cédula", move.display_name))
                continue

            data = amounts[move.id]
            sign = 1 if move.move_type == 'in_invoice' else -1

            service_amount = amt(data.get('service_amount'), sign)
            good_amount = amt(data.get('good_amount'), sign)
            itbis_invoiced = amt(data.get('itbis_invoiced'), sign)
            itbis_cost = amt(data.get('itbis_cost'), sign)
            # Credit notes leave Fecha Pago empty: their reconciliation points back to
            # the original invoice, and a payment date preceding the NCF date is
            # rejected by DGII's validator.
            payment_date = data.get('payment_date') if move.move_type == 'in_invoice' else None

            rows.append([
                self._l10n_do_format_rnc(identifier),                             # 1     RNC o Cédula
                id_type,                                                          # 2     Tipo Id
                self._l10n_do_zfill_optional(move.l10n_do_purchase_type),         # 3     Tipo Bienes y Servicios Comprados
                move._l10n_do_get_ncf(),                                          # 4     NCF
                move.reversed_entry_id._l10n_do_get_ncf(),                        # 5     NCF Documento Modificado
                move.invoice_date.strftime('%Y%m%d'),                             # 6     Fecha Comprobante
                payment_date.strftime('%Y%m%d') if payment_date else '',          # 7     Fecha Pago
                float_repr(service_amount, 2),                                    # 8     Monto Facturado en Servicios
                float_repr(good_amount, 2),                                       # 9     Monto Facturado en Bienes
                float_repr(service_amount + good_amount, 2),                      # 10    Total Monto Facturado
                float_repr(itbis_invoiced, 2),                                    # 11    ITBIS Facturado
                self._l10n_do_format_optional(amt(data.get('itbis_withheld'), -sign)),  # 12    ITBIS Retenido
                '',                                                               # 13    ITBIS sujeto a Proporcionalidad
                self._l10n_do_format_optional(itbis_cost),                        # 14    ITBIS llevado al Costo
                float_repr(itbis_invoiced - itbis_cost, 2),                       # 15    ITBIS por Adelantar
                '',                                                               # 16    ITBIS percibido en compras
                self._l10n_do_zfill_optional(data.get('isr_type')),               # 17    Tipo de Retención en ISR
                self._l10n_do_format_optional(amt(data.get('isr_withheld'), -sign)),  # 18    Monto Retención Renta
                '',                                                               # 19    ISR Percibido en compras
                self._l10n_do_format_optional(amt(data.get('isc_amount'), sign)),  # 20    Impuesto Selectivo al Consumo
                '',                                                               # 21    Otros Impuesto/Tasas
                self._l10n_do_format_optional(amt(data.get('tip_amount'), sign)),  # 22    Monto Propina Legal
                self._l10n_do_zfill_optional(move.l10n_do_payment_type),          # 23    Forma de Pago
            ])

        if errors:
            raise UserError(self.env._(
                "The following entries cannot be reported on the 606:\n%s",
                '\n'.join(errors),
            ))
        return rows

    @api.model
    def _l10n_do_get_606_amounts(self, moves):
        """ Aggregate every 606 amount column in SQL, as {move_id: {column: value}}.

        The amounts come from three different join shapes (plain invoice lines, line x tax
        grid, line x reconciliation), which cannot share one GROUP BY without multiplying
        each other's rows: run one aggregated query per shape and merge them per move.
        """
        line_amounts = self._l10n_do_get_606_line_amounts(moves)
        grid_amounts = self._l10n_do_get_606_grid_amounts(moves)
        payment_dates = self._l10n_do_get_606_payment_dates(moves)
        return {
            move_id: {
                **line_amounts.get(move_id, {}),
                **grid_amounts.get(move_id, {}),
                **payment_dates.get(move_id, {}),
            }
            for move_id in moves.ids
        }

    @api.model
    def _l10n_do_get_606_line_amounts(self, moves):
        """ Sum per move the goods/services amounts split per product type (lines without a
        product count as services), the ISC/tip amounts (no dedicated tax grid: summed per
        tax group) and take the ISR withholding type of the applied taxes.
        """
        def group_ids(xmlid):
            groups = (
                self.env['account.chart.template'].with_company(company).ref(xmlid, raise_if_not_found=False)
                for company in moves.company_id
            )
            return tuple(group.id for group in groups if group) or (0,)

        query = self.env['account.move.line']._search([('move_id', 'in', moves.ids)])
        aml_t = query.table
        is_service = SQL("(%s IS NULL OR %s = 'service')", aml_t.product_id, aml_t.product_id.product_tmpl_id.type)
        tax_t = aml_t.tax_line_id
        return self._l10n_do_aggregate_by_move(
            query,
            SQL("SUM(%s) FILTER (WHERE %s = 'product' AND %s) AS service_amount", aml_t.balance, aml_t.display_type, is_service),
            SQL("SUM(%s) FILTER (WHERE %s = 'product' AND NOT %s) AS good_amount", aml_t.balance, aml_t.display_type, is_service),
            SQL('SUM(%s) FILTER (WHERE %s IN %s) AS isc_amount', aml_t.balance, tax_t.tax_group_id, group_ids('tax_group_isc')),
            SQL('SUM(%s) FILTER (WHERE %s IN %s) AS tip_amount', aml_t.balance, tax_t.tax_group_id, group_ids('tax_group_tip')),
            SQL('MIN(%(isr_type)s) FILTER (WHERE %(isr_type)s IS NOT NULL) AS isr_type', isr_type=tax_t.l10n_do_isr_type),
        )

    @api.model
    def _l10n_do_get_606_grid_amounts(self, moves):
        """ Sum per move the balance of the lines impacting each group of 606 tax grids. """
        tag_model = self.env['account.account.tag']
        do_country_id = self.env.ref('base.do').id

        def tag_ids(names):
            ids = [tag.id for name in names for tag in tag_model._get_tax_tags(name, do_country_id)]
            return tuple(ids or [0])

        query = self.env['account.move.line']._search([('move_id', 'in', moves.ids)])
        aml_t = query.table
        tag_t = aml_t._join('tax_tag_ids')
        return self._l10n_do_aggregate_by_move(
            query,
            SQL('SUM(%s) FILTER (WHERE %s IN %s) AS itbis_invoiced', aml_t.balance, tag_t.id, tag_ids(ITBIS_PURCHASE_TAGS)),
            SQL('SUM(%s) FILTER (WHERE %s IN %s) AS itbis_cost', aml_t.balance, tag_t.id, tag_ids(ITBIS_COST_TAGS)),
            SQL('SUM(%s) FILTER (WHERE %s IN %s) AS itbis_withheld', aml_t.balance, tag_t.id, tag_ids(ITBIS_WITHHELD_TAGS)),
            SQL('SUM(%s) FILTER (WHERE %s IN %s) AS isr_withheld', aml_t.balance, tag_t.id, tag_ids(ISR_WITHHELD_TAGS)),
        )

    @api.model
    def _l10n_do_get_606_payment_dates(self, moves):
        """ Take per move the date of the last counterpart reconciled with its payable lines. """
        query = self.env['account.move.line']._search([
            ('move_id', 'in', moves.ids),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
        ])
        aml_t = query.table
        debit_counterpart_date = aml_t._join('matched_debit_ids').debit_move_id.date
        credit_counterpart_date = aml_t._join('matched_credit_ids').credit_move_id.date
        return self._l10n_do_aggregate_by_move(
            query,
            # GREATEST ignores NULLs: unpaid moves end up with a NULL payment date
            SQL('MAX(GREATEST(%s, %s)) AS payment_date', debit_counterpart_date, credit_counterpart_date),
        )

    @api.model
    def _l10n_do_aggregate_by_move(self, query, *selects):
        """ Run the aggregated query grouped per move, returning {move_id: {column: value}}. """
        move_id = query.table.move_id
        query.groupby = move_id
        rows = self.env.execute_query_dict(query.select(move_id, *selects))
        return {row.pop('move_id'): row for row in rows}

    @api.model
    def _l10n_do_format_rnc(self, vat):
        """ DGII identifies parties by the bare digits of their RNC/Cédula. """
        return ''.join(filter(str.isdigit, vat or ''))

    @api.model
    def _l10n_do_format_optional(self, amount):
        """ Optional amount columns are left empty rather than reported as zero. """
        return float_repr(amount, 2) if amount else ''

    @api.model
    def _l10n_do_zfill_optional(self, value):
        """ DGII's validator requires these Selection-backed codes as 2-digit
        strings; leave empty values empty rather than zero-padding them into
        a spurious '00' code.
        """
        return value.zfill(2) if value else ''
