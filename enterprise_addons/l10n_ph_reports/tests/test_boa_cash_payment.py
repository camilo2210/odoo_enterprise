# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from odoo import Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.l10n_ph.tests.common import TestPhCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_ph_boa_reports")
class TestPhBoaCashReports(TestAccountReportsCommon, TestPhCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country("ph")
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_local = cls.env["res.partner"].create({
            "name": "Local Customer",
            "vat": "123-456-789-000",
            "street": "123 Rizal Ave",
            "city": "Manila"
        })

        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.bank_account = cls.bank_journal.default_account_id
        cls.ar_account = cls.company_data["default_account_receivable"]
        cls.ap_account = cls.company_data["default_account_payable"]

        cls.receipt_move = cls.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-02-10",
            "journal_id": cls.bank_journal.id,
            "partner_id": cls.partner_local.id,
            "ref": "REC-001",
            "line_ids": [
                Command.create({"name": "Bank Line", "account_id": cls.bank_account.id, "debit": 500.0, "credit": 0.0, "partner_id": cls.partner_local.id}),
                Command.create({"name": "AR Line", "account_id": cls.ar_account.id, "debit": 0.0, "credit": 500.0, "partner_id": cls.partner_local.id}),
            ]
        })
        cls.receipt_move.action_post()

        cls.disbursement_move = cls.env["account.move"].create({
            "move_type": "entry",
            "date": "2025-02-15",
            "journal_id": cls.bank_journal.id,
            "partner_id": cls.partner_local.id,
            "ref": "DISB-001",
            "line_ids": [
                Command.create({"name": "AP Line", "account_id": cls.ap_account.id, "debit": 300.0, "credit": 0.0, "partner_id": cls.partner_local.id}),
                Command.create({"name": "Bank Line", "account_id": cls.bank_account.id, "debit": 0.0, "credit": 300.0, "partner_id": cls.partner_local.id}),
            ]
        })
        cls.disbursement_move.action_post()

    def _get_csv_rows(self, report, options):
        handler = self.env[report.custom_handler_model_name]
        export_data = handler.print_report_to_csv(options)
        return list(csv.reader(io.StringIO(export_data["file_content"].decode("utf-8")), delimiter=","))

    def test_cash_receipt_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_cash_receipt_report")
        options = self._generate_options(report, "2025-02-01", "2025-02-28", {"unfold_all": True})
        self.assertLinesValues(
            report._get_lines(options),
            #   Name,                                   Date,         Code,                   Account Name,           Partner,          Taxpayer ID Number,Address,                 Ref,       Debit,  Credit
            [   0,                                      1,            2,                      3,                      4,                5,                 6,                       7,         8,      9],
            [
                ["Cash Receipts Journal",               "",           "",                     "",                     "",               "",                "",                      "",        500.00, 500.00],
                [ self.receipt_move.name,               "02/10/2025", "",                     "",                     "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "REC-001", 500.00, 500.00],
                [  "AR Line",                           "",           self.ar_account.code,   self.ar_account.name,   "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "REC-001",   0.00, 500.00],
                [  "Bank Line",                         "",           self.bank_account.code, self.bank_account.name, "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "REC-001", 500.00,   0.00],
                [ f"Total {self.receipt_move.name}",    "02/10/2025", "",                     "",                     "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "REC-001", 500.00, 500.00],
                ["Total Cash Receipts Journal",         "",           "",                     "",                     "",               "",                "",                      "",        500.00, 500.00],
            ],
            options,
        )

    def test_cash_receipt_csv_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_cash_receipt_report")
        options = self._generate_options(report, "2025-02-01", "2025-02-28", {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        self.assertEqual(rows, [
            [self.receipt_move.name, "2025-02-10", self.ar_account.code,   self.ar_account.name,   "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "REC-001", "AR Line",   "0.00", "500.00"],
            [self.receipt_move.name, "2025-02-10", self.bank_account.code, self.bank_account.name, "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "REC-001", "Bank Line", "500.00", "0.00"],
        ])

    def test_cash_disbursement_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_cash_disbursement_report")
        options = self._generate_options(report, "2025-02-01", "2025-02-28", {"unfold_all": True})
        self.assertLinesValues(
            report._get_lines(options),
            #   Name,                                       Date,         Code,                   Account Name,           Partner,          Taxpayer ID Number,Address,                 Ref,        Debit,  Credit
            [   0,                                          1,            2,                      3,                      4,                5,                 6,                       7,          8,      9],
            [
                ["Cash Disbursement Journal",               "",           "",                     "",                     "",               "",                "",                      "",         300.00, 300.00],
                [ self.disbursement_move.name,              "02/15/2025", "",                     "",                     "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "DISB-001", 300.00, 300.00],
                [  "AP Line",                               "",           self.ap_account.code,   self.ap_account.name,   "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "DISB-001", 300.00,   0.00],
                [  "Bank Line",                             "",           self.bank_account.code, self.bank_account.name, "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "DISB-001",   0.00, 300.00],
                [ f"Total {self.disbursement_move.name}",   "02/15/2025", "",                     "",                     "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "DISB-001", 300.00, 300.00],
                ["Total Cash Disbursement Journal",         "",           "",                     "",                     "",               "",                "",                      "",         300.00, 300.00],
            ],
            options,
        )

    def test_cash_disbursement_csv_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_cash_disbursement_report")
        options = self._generate_options(report, "2025-02-01", "2025-02-28", {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        self.assertEqual(rows, [
            [self.disbursement_move.name, "2025-02-15", self.ap_account.code,   self.ap_account.name,   "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "DISB-001", "AP Line",   "300.00", "0.00"],
            [self.disbursement_move.name, "2025-02-15", self.bank_account.code, self.bank_account.name, "Local Customer", "123-456-789-000", "123 Rizal Ave, Manila", "DISB-001", "Bank Line", "0.00", "300.00"],
        ])
