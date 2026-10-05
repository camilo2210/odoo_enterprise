# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
from odoo.tests import freeze_time
from odoo.addons.account_asset.tests.common import TestAccountAssetCommon
from odoo.addons.l10n_ph_reports.tests.test_boa_generation import TestPhBoaReports
from odoo.fields import Date
from odoo.tests import tagged
from odoo.tools.date_utils import end_of, start_of


@freeze_time('2026-01-01')
@tagged("post_install_l10n", "post_install", "-at_install", "l10n_ph_boa_reports")
class TestBoaFalReport(TestPhBoaReports, TestAccountAssetCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("l10n_ph_reports_asset.boa_fal_report")

        cls.today = Date.today()
        cls.year_start = start_of(cls.today, "year")
        cls.year_end = end_of(cls.today, "year")

        cls.group_comp = cls.env["account.asset.group"].create({"name": "Computers"})
        cls.group_veh = cls.env["account.asset.group"].create({"name": "Vehicles"})

        cls.asset_comp_run = cls.create_asset(
            value=1000.0, method_number=60, method_period="1", asset_group_id=cls.group_comp.id,
            name="CMP-RUN-001", l10n_ph_fixed_asset_code="FA-CMP-001",
            method="degressive", method_progress_factor=0.3, salvage_value=100.0,
            acquisition_date=cls.year_start, prorata_date=cls.year_start
        )

        cls.asset_veh_run = cls.create_asset(
            value=2000.0, method_number=24, method_period="1", asset_group_id=cls.group_veh.id,
            name="VEH-RUN-001", l10n_ph_fixed_asset_code="FA-VEH-001",
            prorata_computation_type="daily_computation",
            acquisition_date=cls.year_start, prorata_date=cls.year_start
        )

        cls.asset_draft = cls.create_asset(
            value=50000.0, method_number=60, method_period="1",
            name="ASSET-DRAFT-001", l10n_ph_fixed_asset_code="FA-AST-DRAFT",
            acquisition_date=cls.today
        )

        cls.asset_future = cls.create_asset(
            value=5000.0, method_number=5, method_period="12", asset_group_id=cls.group_comp.id,
            name="OUT-RANGE-001", l10n_ph_fixed_asset_code="FA-FUTURE",
            acquisition_date=cls.year_end + relativedelta(days=1),
            prorata_date=cls.year_end + relativedelta(days=1)
        )

        cls.asset_sold = cls.create_asset(
            value=3000.0, method_number=3, method_period="12", asset_group_id=cls.group_comp.id,
            name="CMP-SOLD-001", l10n_ph_fixed_asset_code="FA-CMP-SOLD",
            acquisition_date=cls.year_start, prorata_date=cls.year_start
        )

        cls.asset_full = cls.create_asset(
            value=500.0, method_number=2, method_period="1", asset_group_id=cls.group_veh.id,
            name="VEH-FULL-001", l10n_ph_fixed_asset_code="FA-VEH-FULL",
            prorata_computation_type="none",
            acquisition_date=cls.year_start, prorata_date=cls.year_start
        )

        cls.asset_unposted = cls.create_asset(
            value=4000.0, method_number=4, method_period="12", asset_group_id=cls.group_comp.id,
            name="CMP-UNPOSTED-001", l10n_ph_fixed_asset_code="FA-DRAFT-TEST",
            acquisition_date=cls.year_start, prorata_date=cls.year_start
        )

        cls.asset_unposted.validate()
        cls.asset_future.validate()

        assets_to_auto_post = [
            cls.asset_comp_run,
            cls.asset_veh_run,
            cls.asset_full,
            cls.asset_sold
        ]

        with freeze_time(cls.year_end):
            for asset in assets_to_auto_post:
                asset.validate()

        cls.asset_sold.variant_ids.state = "close"

    def _set_filter(self, options, key, value_id, state):
        for opt in options.get(key, []):
            if str(opt["id"]) == str(value_id):
                opt["selected"] = state

    def test_fal_snapshot(self):
        """Test the default end-of-year snapshot of the Fixed Asset Listing report.
        Verifies that all columns (codes, dates, types, and financial values) render
        correctly, and that draft/unposted moves are correctly excluded by default
        (CMP-UNPOSTED-001 shows 0.00 depreciation).
        """
        options = self._generate_options(self.report, self.year_start, self.year_end, {"all_entries": False})
        d_start = self.year_start.strftime("%m/%d/%Y")
        d_today = self.today.strftime("%m/%d/%Y")
        self.assertLinesValues(
            self.report._get_lines(options),
            #    Name,                        Code,            Type,        Purch Date,   Price,     Start Date,  Accum Depr,Life,          Residual
            [    0,                           1,               2,           3,            4,         5,           6,         7,             8],
            [
                ["Fixed Asset Listing",       "",              "",          "",           60500.0,   "",          2770.0,    "",            100.0],
                ["ASSET-DRAFT-001",           "FA-AST-DRAFT",  "",          d_today,      50000.0,   d_start,        0.0,    "60 Month",      0.0],
                ["CMP-RUN-001",               "FA-CMP-001",    "Computers", d_start,       1000.0,   d_start,      270.0,    "60 Month",    100.0],
                ["CMP-SOLD-001",              "FA-CMP-SOLD",   "Computers", d_start,       3000.0,   d_start,     1000.0,    "3 Year",        0.0],
                ["CMP-UNPOSTED-001",          "FA-DRAFT-TEST", "Computers", d_start,       4000.0,   d_start,        0.0,    "4 Year",        0.0],
                ["VEH-FULL-001",              "FA-VEH-FULL",   "Vehicles",  d_start,        500.0,   d_start,      500.0,    "2 Month",       0.0],
                ["VEH-RUN-001",               "FA-VEH-001",    "Vehicles",  d_start,       2000.0,   d_start,     1000.0,    "24 Month",      0.0],
                ["Total Fixed Asset Listing", "",              "",          "",           60500.0,   "",          2770.0,    "",            100.0],
            ],
            options=options,
        )

    def test_fal_draft_inclusion(self):
        """Test the report with 'Include Draft Entries' enabled.
        CMP-UNPOSTED-001 should show calculated depreciation (1000.0) from unposted moves.
        """
        options = self._generate_options(self.report, self.year_start, self.year_end, {"all_entries": True})
        self.assertLinesValues(
            self.report._get_lines(options),
            #    Name,                          Accum Depr
            [    0,                             6],
            [
                ["Fixed Asset Listing",         3770.0],
                [ "ASSET-DRAFT-001",               0.0],
                [ "CMP-RUN-001",                 270.0],
                [ "CMP-SOLD-001",               1000.0],
                [ "CMP-UNPOSTED-001",           1000.0],  # Draft moves are now included
                [ "VEH-FULL-001",                500.0],
                [ "VEH-RUN-001",                1000.0],
                ["Total Fixed Asset Listing",   3770.0],  # Total increases by 1000.0
            ],
            options=options,
        )

    def test_fal_evolution_mid_year(self):
        """Test the report at MID-YEAR (June 30) for dynamic calculation."""
        mid_year_date = self.year_start + relativedelta(months=6, days=-1)
        options = self._generate_options(self.report, self.year_start, mid_year_date)
        options["all_entries"] = False
        self.assertLinesValues(
            self.report._get_lines(options),
            #    Name,                         Price,   Accum Depr, Residual
            [    0,                                4,            6,        8],
            [
                ["Fixed Asset Listing",       60500.0,     1130.89,    100.0],
                [ "ASSET-DRAFT-001",          50000.0,         0.0,      0.0],
                [ "CMP-RUN-001",               1000.0,       135.0,    100.0],
                [ "CMP-SOLD-001",              3000.0,         0.0,      0.0],
                [ "CMP-UNPOSTED-001",          4000.0,         0.0,      0.0],
                [ "VEH-FULL-001",               500.0,       500.0,      0.0],
                [ "VEH-RUN-001",               2000.0,      495.89,      0.0],
                ["Total Fixed Asset Listing", 60500.0,     1130.89,    100.0],
            ],
            options=options,
        )

    def test_fal_csv_snapshot(self):
        """Test the report's CSV export which is practically the same just without the top groupby line."""
        options = self._generate_options(self.report, self.year_start, self.year_end, {"all_entries": False})
        rows = self._get_csv_rows(self.report, options)
        d_start = self.year_start.strftime("%m/%d/%Y")
        d_today = self.today.strftime("%m/%d/%Y")
        self.assertEqual(rows, [
            # Name,               FA Code,         Type,        Purch Date,   Cost,         Start,         Depr,      Life,            Residual
            ["ASSET-DRAFT-001",   "FA-AST-DRAFT",  "",          d_today,      "50000.00",   d_start,          "0.00", "60 Month",       "0.00"],
            ["CMP-RUN-001",       "FA-CMP-001",    "Computers", d_start,       "1000.00",   d_start,        "270.00", "60 Month",     "100.00"],
            ["CMP-SOLD-001",      "FA-CMP-SOLD",   "Computers", d_start,       "3000.00",   d_start,       "1000.00", "3 Year",         "0.00"],
            ["CMP-UNPOSTED-001",  "FA-DRAFT-TEST", "Computers", d_start,       "4000.00",   d_start,          "0.00", "4 Year",         "0.00"],
            ["VEH-FULL-001",      "FA-VEH-FULL",   "Vehicles",  d_start,        "500.00",   d_start,        "500.00", "2 Month",        "0.00"],
            ["VEH-RUN-001",       "FA-VEH-001",    "Vehicles",  d_start,       "2000.00",   d_start,       "1000.00", "24 Month",       "0.00"],
        ])

    def test_fal_filter_status_running_only(self):
        """Test the 'Running' asset state filter.
        Verifies that only assets currently in an open/running state are included,.
        """
        options = self._generate_options(self.report, self.year_start, self.year_end)
        self._set_filter(options, "asset_states", "open", True)
        self.assertLinesValues(
            self.report._get_lines(options),
            [0],
            [
                ["Fixed Asset Listing"],
                [   "CMP-RUN-001"],
                [   "CMP-UNPOSTED-001"],
                [   "VEH-FULL-001"],
                [   "VEH-RUN-001"],
                ["Total Fixed Asset Listing"],
            ],
            options=options,
        )

    def test_fal_filter_group_computers_only(self):
        """Test the Asset Group filter.
        Verifies that filtering by the 'Computers' model return correctly.
        """
        options = self._generate_options(self.report, self.year_start, self.year_end)
        self._set_filter(options, "asset_groups", self.group_comp.id, True)
        self.assertLinesValues(
            self.report._get_lines(options),
            [0],
            [
                ["Fixed Asset Listing"],
                [   "CMP-RUN-001"],
                [   "CMP-SOLD-001"],
                [   "CMP-UNPOSTED-001"],
                ["Total Fixed Asset Listing"],
            ],
            options=options,
        )

    def test_fal_old_running_asset_overlap(self):
        """Test historical asset inclusion/exclusion.
        Verifies that:
        1. An asset acquired 2 years ago (OLD-RUN-001) appears with correct
           Accumulated Depreciation (2 years prior + 1 current year).
        2. An ancient asset (ANCIENT-001) fully depreciated 5 years ago is excluded.
        """
        two_years_ago = self.year_start - relativedelta(years=2)
        asset_old = self.create_asset(
            value=12000.0,
            method_period="12",
            method_number=5,
            asset_group_id=self.group_comp.id,
            name="OLD-RUN-001",
            l10n_ph_fixed_asset_code="FA-OLD-001",
            acquisition_date=two_years_ago,
            prorata_date=two_years_ago
        )
        ancient_date = self.year_start - relativedelta(years=10)
        asset_ancient = self.create_asset(
            value=1000.0, method_number=5, method_period="12",
            name="ANCIENT-001", acquisition_date=ancient_date, prorata_date=ancient_date
        )
        with freeze_time(self.year_end):
            asset_old.validate()
            asset_ancient.validate()

        options = self._generate_options(self.report, self.year_start, self.year_end)
        self.assertLinesValues(
            self.report._get_lines(options),
            # Name,                         Price,   Accum Depr, Residual
            [0,                                 4,            6,        8],
            [
                ["Fixed Asset Listing",       72500.0,     9970.0,      100.0],
                [ "ASSET-DRAFT-001",          50000.0,        0.0,        0.0],
                [ "CMP-RUN-001",               1000.0,      270.0,      100.0],
                [ "CMP-SOLD-001",              3000.0,     1000.0,        0.0],
                [ "CMP-UNPOSTED-001",          4000.0,        0.0,        0.0],
                [ "OLD-RUN-001",              12000.0,     7200.0,        0.0],
                [ "VEH-FULL-001",               500.0,      500.0,        0.0],
                [ "VEH-RUN-001",               2000.0,     1000.0,        0.0],
                ["Total Fixed Asset Listing", 72500.0,     9970.0,      100.0],
            ],
            options=options,
        )

    def test_fal_land_indefinite_life(self):
        """Test non-depreciating assets (Duration = 0).
        Verifies that Land appears even if acquired long before the report period,
        maintaining a 0.00 Accumulated Depreciation balance.
        """
        old_date = self.year_start - relativedelta(years=5)
        asset_land = self.create_asset(
            value=1000000.0, method_number=0, method="no_depreciation", method_period="12",
            name="LAND-001", l10n_ph_fixed_asset_code="FA-LAND",
            acquisition_date=old_date, prorata_date=old_date
        )
        asset_land.validate()
        options = self._generate_options(self.report, self.year_start, self.year_end)
        self.assertLinesValues(
            self.report._get_lines(options),
            # Name,                         Price,   Accum Depr, Residual
            [0,                                 4,            6,        8],
            [
                ["Fixed Asset Listing",       1060500.0,   2770.0,      100.0],
                [ "ASSET-DRAFT-001",            50000.0,      0.0,        0.0],
                [ "CMP-RUN-001",                 1000.0,    270.0,      100.0],
                [ "CMP-SOLD-001",                3000.0,   1000.0,        0.0],
                [ "CMP-UNPOSTED-001",            4000.0,      0.0,        0.0],
                [ "LAND-001",                 1000000.0,      0.0,        0.0],
                [ "VEH-FULL-001",                 500.0,    500.0,        0.0],
                [ "VEH-RUN-001",                 2000.0,   1000.0,        0.0],
                ["Total Fixed Asset Listing", 1060500.0,   2770.0,      100.0],
            ],
            options=options,
        )

    def test_fal_analytic_draft_visibility(self):
        """Test Analytic Account filtering with Draft entries.
        Verifies that 'Draft' depreciation entries remain properly linked and visible
        in the report even when an Analytic Filter is applied to the view.
        """
        analytic_plan = self.env["account.analytic.plan"].create({"name": "Plan A"})
        analytic_account = self.env["account.analytic.account"].create({
            "name": "Dept Sales",
            "plan_id": analytic_plan.id,
        })
        self.asset_draft.write({"analytic_distribution": {analytic_account.id: 100}})
        options = self._generate_options(self.report, self.year_start, self.year_end, {"all_entries": True})
        options["analytic_accounts"] = [analytic_account.id]
        self.assertLinesValues(
            self.report._get_lines(options),
            #    Name,                          Accum Depr
            [    0,                             6],
            [
                ["Fixed Asset Listing",         3770.0],
                [ "ASSET-DRAFT-001",               0.0],
                [ "CMP-RUN-001",                 270.0],
                [ "CMP-SOLD-001",               1000.0],
                [ "CMP-UNPOSTED-001",           1000.0],
                [ "VEH-FULL-001",                500.0],
                [ "VEH-RUN-001",                1000.0],
                ["Total Fixed Asset Listing",   3770.0],
            ],
            options=options,
        )
