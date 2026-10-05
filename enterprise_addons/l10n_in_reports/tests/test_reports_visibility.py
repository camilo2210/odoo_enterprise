from odoo.addons.l10n_in_reports.tests.common import L10nInTestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nINReportsVisibility(L10nInTestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.gstr_reports = [
            cls.env.ref('l10n_in_reports.account_report_gstr1').id,
            cls.env.ref('l10n_in_reports.account_report_gstr2b').id,
            cls.env.ref('l10n_in_reports.account_report_gstr3b').id
        ]
        cls.tcs_tds_reports = [
            cls.env.ref('l10n_in.tcs_report').id,
            cls.env.ref('l10n_in.tds_report').id
        ]
        cls.new_in_company = cls.env['res.company'].create({
            'name': 'New India Company',
            'country_id': cls.country_in.id,
        })
        cls.user.write({
            'company_ids': [cls.default_company.id, cls.new_in_company.id],
            'company_id': cls.default_company.id,
        })

    def test_visibility_of_all_indian_reports(self):
        # Ensure all GSTR reports and TDS/TCS reports are visible for Indian company.
        self.default_company.l10n_in_tcs_feature = True
        self.default_company.l10n_in_tds_feature = True
        self.default_company.l10n_in_gst_efiling_feature = True
        generic_tax_report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        in_reports = self.gstr_reports + self.tcs_tds_reports
        available_in_reports = [v for v in options['available_variants'] if v['id'] in in_reports]

        self.assertEqual(
            len(available_in_reports), 5,
            "All GSTR and TCS/TDS variants should be available in the generic tax report's variants"
        )

    def test_visibility_of_TDS_TCS(self):
        # Ensure TCS/TDS reports are not visible when TCS/TDS feature is disable for Indian company.
        self.default_company.l10n_in_tcs_feature = False
        self.default_company.l10n_in_tds_feature = False

        generic_tax_report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        available_tcs_tds_reports = [v for v in options['available_variants'] if v['id'] in self.tcs_tds_reports]

        self.assertEqual(
            len(available_tcs_tds_reports), 0,
            "TCS/TDS variants should not be available in the generic tax report's variants"
        )

    def test_visibility_of_GSTR(self):
        # Ensure all GSTR reports are not visible when GSTR Report feature is disable for Indian company.
        self.default_company.l10n_in_gst_efiling_feature = False

        generic_tax_report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        available_gstr_reports = [v for v in options['available_variants'] if v['id'] in self.gstr_reports]

        self.assertEqual(
            len(available_gstr_reports), 0,
            "All GSTR report variants should not be available in the generic tax report's variants"
        )

    def test_visibility_of_TDS_TCS_for_multicompany(self):
        # Ensure TCS/TDS both reports are visible when TCS feature is enable in one company and TDS feature is enable in another Indian company.
        self.default_company.l10n_in_tcs_feature = True
        self.default_company.l10n_in_tds_feature = False
        self.new_in_company.l10n_in_tds_feature = True

        generic_tax_report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        available_tcs_tds_reports = [v for v in options['available_variants'] if v['id'] in self.tcs_tds_reports]

        self.assertEqual(
            len(available_tcs_tds_reports), 2,
            "TCS/TDS variants should be available in the generic tax report's variants"
        )

    def test_visibility_of_GSTR_for_multicompany(self):
        # Ensure all GSTR reports are visible when GSTR Reposrt feature is disable for one company and disable in othar Indian company.
        self.default_company.l10n_in_gst_efiling_feature = False
        self.new_in_company.l10n_in_gst_efiling_feature = True

        generic_tax_report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        available_gstr_reports = [v for v in options['available_variants'] if v['id'] in self.gstr_reports]

        self.assertEqual(
            len(available_gstr_reports), 3,
            "All GSTR report variants should be available in the generic tax report's variants"
        )
