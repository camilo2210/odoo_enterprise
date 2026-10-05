from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import file_open

from odoo.addons.account_reports.models.account_report import (
    AccountReportFileDownloadException,
)
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.l10n_ae_faf.models.account_general_ledger import (
    AccountGeneralLedgerReportHandler,
)

_original__l10n_ae_faf_fetch_data = AccountGeneralLedgerReportHandler._l10n_ae_faf_fetch_data
_original__l10n_ae_faf_get_company_info_lines = AccountGeneralLedgerReportHandler._l10n_ae_faf_get_company_info_lines


def _l10n_ae_faf_fetch_data_patched(self, *args):
    res = _original__l10n_ae_faf_fetch_data(self, *args)
    for move in res['moves'].values():
        move['id'] = '0'  # Set move id to 0 since it's DB dependent

    return res


def _l10n_ae_faf_get_company_info_lines_patched(self, *args):
    res = _original__l10n_ae_faf_get_company_info_lines(self, *args)
    # Set Odoo version to be 0 to avoid the need to update in the future
    args[1][2] = (
        *args[1][2][:10],
        '0',
        *args[1][2][11:],
    )
    return res


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAeFafReport(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('ae')
    def setUpClass(cls):
        super().setUpClass()

        company = cls.company_data['company']
        company_2 = cls.company_data_2['company']
        cls.ReportException = AccountReportFileDownloadException
        cls.ReportModel = cls.env.ref('account_reports.general_ledger_report')
        cls.ReportHandlerModel = cls.env[cls.ReportModel.custom_handler_model_name]
        cls.report_handler = cls.ReportHandlerModel.with_company(company)
        cls.report_handler_2 = cls.ReportHandlerModel.with_company(company_2)

        cls.partner_c = cls.env['res.partner'].create({
            'name': 'partner_c',
            'country_id': cls.env.ref('base.ae').id,
        })

        cls.tax_agency = cls.env['res.partner'].create({
            'name': 'AE Tax Agency',
            'l10n_ae_name_ar': 'وكالة الضرائب',
            'l10n_ae_tax_agency_number': '123',
        })

        cls.tax_agent = cls.env['res.partner'].create({
            'name': 'AE Tax Agent',
            'l10n_ae_name_ar': 'وكيل الضرائب',
            'ref': '321',
        })

        cls.tax_agency_2 = cls.env['res.partner'].create({
            'name': 'AE Tax Agency 2',
            'l10n_ae_name_ar': 'وكالة الضرائب 2',
        })

        cls.tax_agent_2 = cls.env['res.partner'].create({
            'name': 'AE Tax Agent 2',
            'l10n_ae_name_ar': 'وكيل الضرائب 2',
        })

        company.write({
            'l10n_ae_tax_agency': cls.tax_agency.id,
            'l10n_ae_tax_agent': cls.tax_agent.id,
            'l10n_ae_name_ar': 'شركة 1',
        })

        company_2.write({
            'l10n_ae_tax_agency': cls.tax_agency_2.id,
            'l10n_ae_tax_agent': cls.tax_agent_2.id,
            'l10n_ae_name_ar': 'شركة 2',
        })

        (cls.company_data['default_tax_sale'] + cls.company_data['default_tax_purchase']).write({'l10n_ae_tax_code': 'SR'})

        cls.invoices = cls.env['account.move'].create([
            {
                'move_type': 'out_invoice',
                'invoice_date': '2025-10-01',
                'date': '2025-10-01',
                'partner_id': cls.partner_a.id,
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 5.0,
                    'price_unit': 1000.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_sale'].ids)],
                })],
            },
            {
                'move_type': 'out_refund',
                'invoice_date': '2025-10-03',
                'date': '2025-10-03',
                'partner_id': cls.partner_a.id,
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 3.0,
                    'price_unit': 1000.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_sale'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2025-10-30',
                'date': '2025-10-30',
                'partner_id': cls.partner_b.id,
                'l10n_ae_import_permit_number': '123',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_b.id,
                    'quantity': 10.0,
                    'price_unit': 800.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                })],
            },
        ])

        cls.invoices |= cls.env['account.move'].with_company(company_2).create([
            {
                'move_type': 'out_invoice',
                'invoice_date': '2025-11-02',
                'date': '2025-11-02',
                'partner_id': cls.partner_c.id,
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 5.0,
                    'price_unit': 1000.0,
                    'tax_ids': [Command.set(cls.company_data_2['default_tax_sale'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2025-11-03',
                'date': '2025-11-03',
                'partner_id': cls.partner_b.id,
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_b.id,
                    'quantity': 10.0,
                    'price_unit': 800.0,
                    'tax_ids': [Command.set(cls.company_data_2['default_tax_purchase'].ids)],
                })],
            },
        ])

        cls.invoices.action_post()

    def _l10n_ae_faf_compare_csv(self, report_csv, csv_file):
        report_csv_content = report_csv['file_content']
        with file_open(f'{self.test_module}/tests/expected_csv/{csv_file}', 'rb') as fp:
            test_csv_content = fp.read()
        self.assertEqual(report_csv_content, test_csv_content, 'Generated CSV does not match expected CSV')

    @patch('odoo.addons.l10n_ae_faf.models.account_general_ledger.AccountGeneralLedgerReportHandler._l10n_ae_faf_fetch_data', _l10n_ae_faf_fetch_data_patched)
    @patch('odoo.addons.l10n_ae_faf.models.account_general_ledger.AccountGeneralLedgerReportHandler._l10n_ae_faf_get_company_info_lines', _l10n_ae_faf_get_company_info_lines_patched)
    @freeze_time('2025-12-01')
    def _l10n_ae_faf_generate_report(self, options):
        return self.report_handler.l10n_ae_export_faf_csv(options)

    def test_l10n_ae_faf_report_values(self):
        options = self._generate_options(self.ReportModel, date_from='2025-10-01', date_to='2025-10-31')
        report_csv = self._l10n_ae_faf_generate_report(options)
        self._l10n_ae_faf_compare_csv(report_csv, 'faf_report.csv')

    def test_l10n_ae_faf_report_warnings(self):
        options = self._generate_options(self.ReportModel, date_from='2025-11-01', date_to='2025-11-30')
        report = self.env['account.report'].browse(options['report_id'])
        vals = self.report_handler_2._l10n_ae_faf_fetch_data(report, options)
        errors = self.report_handler_2._l10n_ae_faf_get_errors(vals)

        for warning in [
            'l10n_ae_tax_missing_categ_code',
            'l10n_ae_move_missing_permit',
            'l10n_ae_partner_missing_state',
            'l10n_ae_tax_agent_missing_ref',
            'l10n_ae_tax_agency_missing_company_registry',
        ]:
            self.assertTrue(errors.get(warning), f'Warning {warning} was not raised')
