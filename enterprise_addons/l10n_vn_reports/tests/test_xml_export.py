from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_vn_reports.tests.test_tax_report import TestL10nVnTaxReport


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nVnXmlExport(TestL10nVnTaxReport):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.vat = '0100109106'
        cls.handler = cls.env['l10n_vn_reports.form_01_gtgt.report.handler']
        cls.default_wizard_input = {
            'business_activity': 'ordinary',
            'business_activity_code': '00',
            'business_activity_label': 'Hoạt động sản xuất kinh doanh thông thường',
            'first_time': True,
            'adjustment_no': 0,
            'show_dependent_unit': False,
            'dependent_unit_name': '',
            'dependent_unit_tax_code': '',
            'province_code': '',
            'province_name': '',
            'district': '',
            'ward': '',
        }

    def _export_xml(self, date_from, date_to, wizard_data=None):
        options = self._generate_options(self.tax_report, date_from, date_to)
        options['l10n_vn_xml_export'] = {**self.default_wizard_input, **(wizard_data or {})}
        return self.handler.export_tax_report_to_xml(options)['file_content'].decode()

    def test_xml_export_missing_vat_raises(self):
        self.env.company.vat = False
        options = self._generate_options(self.tax_report, '2026-05-01', '2026-05-31')
        options['l10n_vn_xml_export'] = self.default_wizard_input.copy()
        with self.assertRaises(UserError):
            self.handler.export_tax_report_to_xml(options)

    @freeze_time('2026-05-31')
    def test_xml_export_monthly_period(self):
        xml = self._export_xml('2026-05-01', '2026-05-31')
        self.assertIn('<kieuKy>M</kieuKy>', xml)
        self.assertIn('<kyKKhai>05/2026</kyKKhai>', xml)
        self.assertIn(f'<mst>{self.env.company.vat}</mst>', xml)
        self.assertIn('<maTKhai>842</maTKhai>', xml)
        self.assertIn('<loaiTKhai>C</loaiTKhai>', xml)

    @freeze_time('2026-06-30')
    def test_xml_export_quarterly_period(self):
        xml = self._export_xml('2026-04-01', '2026-06-30')
        self.assertIn('<kieuKy>Q</kieuKy>', xml)
        self.assertIn('<kyKKhai>2/2026</kyKKhai>', xml)

    @freeze_time('2026-05-31')
    def test_xml_export_appendix_included(self):
        for move_type, tax in [
            ('in_invoice', self.tax_purchase_8),
            ('out_invoice', self.tax_sale_8),
        ]:
            self._create_invoice(
                move_type=move_type,
                invoice_date='2026-05-15',
                post=True,
                invoice_line_ids=[self._prepare_invoice_line(price_unit=1000000, tax_ids=[tax.id])],
            )
        xml = self._export_xml('2026-05-01', '2026-05-31')
        self.assertIn('<PL_NQ142_GTGT>', xml)

    @freeze_time('2026-05-31')
    def test_xml_export_appendix_absent(self):
        self._create_invoice(
            move_type='out_invoice',
            invoice_date='2026-05-15',
            post=True,
            invoice_line_ids=[self._prepare_invoice_line(price_unit=1000000, tax_ids=[self.tax_sale_10.id])],
        )
        xml = self._export_xml('2026-05-01', '2026-05-31')
        self.assertNotIn('<PL_NQ142_GTGT>', xml)
