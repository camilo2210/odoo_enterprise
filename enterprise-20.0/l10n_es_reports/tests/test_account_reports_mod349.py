from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo import fields, Command

# A practical example from the AEAT can be found here:
# https://sede.agenciatributaria.gob.es/Sede/en_gb/ayuda/manuales-videos-folletos/manuales-practicos/manual-iva-2023/capitulo-09-declaraciones-informativas-iva-349/declaracion-recapitulativa-operac-intracomunitarias-modelo-349/supuesto-practico-modelo-349.html
# This test follows the described operations and asserts the expected values from this example.


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nEsMod349Report(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('es')
    def setUpClass(cls):
        super().setUpClass()
        # Partners
        cls.partner_nl = cls.env['res.partner'].create({
            'name': 'Dutch Biz',
            'vat': 'NL123456782B90',
            'country_id': cls.env.ref('base.nl').id,
        })
        cls.partner_pt = cls.env['res.partner'].create({
            'name': 'Portuguese Biz',
            'vat': 'PT123456789',
            'country_id': cls.env.ref('base.pt').id,
        })

        # Taxes
        cls.mod349_a = cls.env['account.tax'].search([
            ('name', '=', '0% EU G'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', cls.env.company.id)
        ], limit=1)
        cls.mod349_e = cls.env['account.tax'].search([
            ('name', '=', '0% EU G'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.env.company.id)
        ], limit=1)
        cls.mod349_t = cls.env['account.tax'].search([
            ('name', '=', '0% EU EXEMPT T'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.env.company.id)
        ], limit=1)
        cls.mod349_s = cls.env['account.tax'].search([
            ('name', '=', '0% EU S'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.env.company.id)
        ], limit=1)

        cls.handler = cls.env['l10n_es.mod349.tax.report.handler']
        cls.report = cls.env.ref('l10n_es_reports.mod_349')

    def _create_mod349_move(self, move_type, partner, date, amount, tax):
        """ Helper to create and post moves with proper tax tags """
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': date,
            'date': date,
            'line_ids': [Command.create({
                'price_unit': amount,
                'quantity': 1,
                'tax_ids': [Command.set(tax.ids)],
            })]
        })
        move.action_post()
        return move

    def test_modelo_349_aeat_example(self):
        # 1. Purchases two batches of goods from the Dutch businessman NL123456789100, one on 12 May for an amount of 3,455.25 euros
        #    and another on 15 May for an amount of 2,841.91 euros  (tag A)
        inv_nl_1 = self._create_mod349_move('in_invoice', self.partner_nl, '2023-05-12', 3455.25, self.mod349_a)
        self._create_mod349_move('in_invoice', self.partner_nl, '2023-05-15', 2841.91, self.mod349_a)

        # 2. Makes a delivery of machines to the Portuguese businessman PT123456789, valued at 3,344.55 euros (tag E)
        self._create_mod349_move('out_invoice', self.partner_pt, '2023-05-20', 3344.55, self.mod349_e)

        # 3. Makes a triangular Operation (Tag T): purchase from Greece, delivered to Portugal
        self._create_mod349_move('out_invoice', self.partner_pt, '2023-05-22', 10609.31, self.mod349_t)

        # 4. Does an appraisal for a Portuguese businessman PT123456789 for an amount of 5,000 euros (tag S)
        self._create_mod349_move('in_invoice', self.partner_pt, '2023-05-25', 5000.00, self.mod349_s)

        # 5. Cancellation of first Dutch transaction in September
        refund_wizard = self.env['account.move.reversal'].with_context(
            active_ids=inv_nl_1.ids, active_model='account.move'
        ).create({
            'date': fields.Date.to_date('2023-09-01'),
            'journal_id': inv_nl_1.journal_id.id,
        })
        refund_res = refund_wizard.refund_moves()
        refund_nl = self.env['account.move'].browse(refund_res['res_id'])
        refund_nl.action_post()

        # --- TESTS ---
        options_may = self._generate_options(self.report, '2023-05-01', '2023-05-31')
        self.assertLinesValues(
            self.report._get_lines(options_may),
            [0,                                                                                                                                   1],
            [
                ('Summary',                                                                                                                      ''),
                ('Total number of intra-community operators',                                                                                     4),  # Grouped by partners
                ('Total amount of intra-community operations',                                                                             25251.02),
                ('Total number of intra-community refund operators',                                                                              0),
                ('Amount of intra-community refund operations',                                                                                   0),
                ('Invoices',                                                                                                                     ''),
                ('E. Intra-community sales',                                                                                                3344.55),
                ('A. Intra-community purchases subject to taxes',                                                                           6297.16),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                     10609.31),
                ('S. Intra-community sales of services carried out by the declarant',                                                       5000.00),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Transfers of goods made under consignment sales contracts.',                                                                 0),
                ('D. Returns of goods previously sent from the TAI',                                                                              0),
                ('C. Replacements of goods',                                                                                                      0),
                ('Refunds',                                                                                                                      ''),
                ('E. Intra-community sales refunds',                                                                                              0),
                ('A. Intra-community purchases subject to taxes',                                                                                 0),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Rectifications of transfers of goods made under consignment sale contracts.',                                                0),
                ('D. Rectifications of returned goods previously sent from the TAI',                                                              0),
                ('C. Rectifications for replacement of goods',                                                                                    0),
            ],
            options_may
        )

        options_sept = self._generate_options(self.report, '2023-09-01', '2023-09-30')
        self.assertLinesValues(
            self.report._get_lines(options_sept),
            [0,                                                                                                                                   1],
            [
                ('Summary',                                                                                                                      ''),
                ('Total number of intra-community operators',                                                                                     0),
                ('Total amount of intra-community operations',                                                                                    0),
                ('Total number of intra-community refund operators',                                                                              1),
                ('Amount of intra-community refund operations',                                                                             3455.25),
                ('Invoices',                                                                                                                     ''),
                ('E. Intra-community sales',                                                                                                      0),
                ('A. Intra-community purchases subject to taxes',                                                                                 0),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Transfers of goods made under consignment sales contracts.',                                                                 0),
                ('D. Returns of goods previously sent from the TAI',                                                                              0),
                ('C. Replacements of goods',                                                                                                      0),
                ('Refunds',                                                                                                                      ''),
                ('E. Intra-community sales refunds',                                                                                              0),
                ('A. Intra-community purchases subject to taxes',                                                                           3455.25),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Rectifications of transfers of goods made under consignment sale contracts.',                                                0),
                ('D. Rectifications of returned goods previously sent from the TAI',                                                              0),
                ('C. Rectifications for replacement of goods',                                                                                    0),
            ],
            options_sept
        )

    def test_modelo_349_credit_notes(self):
        # 1. Purchases two batches of goods from the Dutch businessman NL123456789100, one on 1st May for an amount of 300 euros
        #    and another on 15 May for an amount of 1000 euros  (tag A)
        inv_1 = self._create_mod349_move('in_invoice', self.partner_nl, '2023-05-01', 300, self.mod349_a)
        inv_2 = self._create_mod349_move('in_invoice', self.partner_nl, '2023-05-15', 1000, self.mod349_a)

        # 2. Makes a refund for 500€, fully cancelling the invoice of 300€
        refund_1 = self._create_mod349_move('in_refund', self.partner_nl, '2023-05-015', 500, self.mod349_a)

        to_reconcile = (refund_1 | inv_1).line_ids.filtered(lambda l: l.account_id.reconcile)
        to_reconcile.reconcile()
        self.assertEqual(inv_1.line_ids.filtered(lambda l: l.account_id.reconcile).amount_residual, 0.0)

        # --- TESTS ---
        options_may = self._generate_options(self.report, '2023-05-01', '2023-05-31')
        self.assertLinesValues(
            self.report._get_lines(options_may),
            [0,                                                                                                                                   1],
            [
                ('Summary',                                                                                                                      ''),
                ('Total number of intra-community operators',                                                                                     1),  # Grouped by partners
                ('Total amount of intra-community operations',                                                                                 1000),
                ('Total number of intra-community refund operators',                                                                              1),
                ('Amount of intra-community refund operations',                                                                                 200),
                ('Invoices',                                                                                                                     ''),
                ('E. Intra-community sales',                                                                                                      0),
                ('A. Intra-community purchases subject to taxes',                                                                              1000),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Transfers of goods made under consignment sales contracts.',                                                                 0),
                ('D. Returns of goods previously sent from the TAI',                                                                              0),
                ('C. Replacements of goods',                                                                                                      0),
                ('Refunds',                                                                                                                      ''),
                ('E. Intra-community sales refunds',                                                                                              0),
                ('A. Intra-community purchases subject to taxes',                                                                               200),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Rectifications of transfers of goods made under consignment sale contracts.',                                                0),
                ('D. Rectifications of returned goods previously sent from the TAI',                                                              0),
                ('C. Rectifications for replacement of goods',                                                                                    0),
            ],
            options_may
        )

        # reconcile the refund and inv_2, partially refunding the invoice of 1000€
        to_reconcile = (refund_1 | inv_2).line_ids.filtered(lambda l: l.account_id.reconcile)
        to_reconcile.reconcile()
        self.assertEqual(refund_1.line_ids.filtered(lambda l: l.account_id.reconcile).amount_residual, 0.0)

        # need to clear the cache dedicated to the report, as the test is run in a single transaction
        del self.env.cr.cache['_custom_modelo349_query']

        self.assertLinesValues(
            self.report._get_lines(options_may),
            [0,                                                                                                                                   1],
            [
                ('Summary',                                                                                                                      ''),
                ('Total number of intra-community operators',                                                                                     1),
                ('Total amount of intra-community operations',                                                                                  800),
                ('Total number of intra-community refund operators',                                                                              0),
                ('Amount of intra-community refund operations',                                                                                   0),
                ('Invoices',                                                                                                                     ''),
                ('E. Intra-community sales',                                                                                                      0),
                ('A. Intra-community purchases subject to taxes',                                                                               800),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Transfers of goods made under consignment sales contracts.',                                                                 0),
                ('D. Returns of goods previously sent from the TAI',                                                                              0),
                ('C. Replacements of goods',                                                                                                      0),
                ('Refunds',                                                                                                                      ''),
                ('E. Intra-community sales refunds',                                                                                              0),
                ('A. Intra-community purchases subject to taxes',                                                                                 0),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Rectifications of transfers of goods made under consignment sale contracts.',                                                0),
                ('D. Rectifications of returned goods previously sent from the TAI',                                                              0),
                ('C. Rectifications for replacement of goods',                                                                                    0),
            ],
            options_may
        )

    def test_modelo_349_payments(self):
        # Ensure invoices paid during the report's period are not removed as the ones with a credit note
        inv_1 = self._create_mod349_move('in_invoice', self.partner_nl, '2023-05-01', 300, self.mod349_a)
        inv_2 = self._create_mod349_move('in_invoice', self.partner_nl, '2023-05-15', 1000, self.mod349_a)

        refund_1 = self._create_mod349_move('in_refund', self.partner_nl, '2023-05-15', 500, self.mod349_a)

        to_reconcile = (refund_1 | inv_1).line_ids.filtered(lambda l: l.account_id.reconcile)
        to_reconcile.reconcile()
        self.assertEqual(inv_1.line_ids.filtered(lambda l: l.account_id.reconcile).amount_residual, 0.0)

        payment_wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=inv_2.id
        ).create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_method_line_id': self.inbound_payment_method_line.id,
            'payment_date': '2023-05-20',
        })
        payment_wizard.action_create_payments()
        self.assertEqual(inv_2.line_ids.filtered(lambda l: l.account_id.reconcile).amount_residual, 0.0)

        # --- TESTS ---
        options_may = self._generate_options(self.report, '2023-05-01', '2023-05-31')
        self.assertLinesValues(
            self.report._get_lines(options_may),
            [0,                                                                                                                                   1],
            [
                ('Summary',                                                                                                                      ''),
                ('Total number of intra-community operators',                                                                                     1),
                ('Total amount of intra-community operations',                                                                                 1000),
                ('Total number of intra-community refund operators',                                                                              1),
                ('Amount of intra-community refund operations',                                                                                 200),
                ('Invoices',                                                                                                                     ''),
                ('E. Intra-community sales',                                                                                                      0),
                ('A. Intra-community purchases subject to taxes',                                                                              1000),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Transfers of goods made under consignment sales contracts.',                                                                 0),
                ('D. Returns of goods previously sent from the TAI',                                                                              0),
                ('C. Replacements of goods',                                                                                                      0),
                ('Refunds',                                                                                                                      ''),
                ('E. Intra-community sales refunds',                                                                                              0),
                ('A. Intra-community purchases subject to taxes',                                                                               200),
                ('T. Sales to other member states exempted of intra-community taxes in case of triangular operations',                            0),
                ('S. Intra-community sales of services carried out by the declarant',                                                             0),
                ('I. Intra-community purchases of services',                                                                                      0),
                ('M. Intra-community sales of goods after an importation exempted of taxes',                                                      0),
                ('H. Intra-community sales of goods after an import exempted of taxes made for the fiscal representative',                        0),
                ('R. Rectifications of transfers of goods made under consignment sale contracts.',                                                0),
                ('D. Rectifications of returned goods previously sent from the TAI',                                                              0),
                ('C. Rectifications for replacement of goods',                                                                                    0),
            ],
            options_may
        )
