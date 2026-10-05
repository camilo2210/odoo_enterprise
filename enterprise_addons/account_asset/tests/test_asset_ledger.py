# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import freeze_time
from odoo.tools.date_utils import end_of

from odoo.addons.account_asset.tests.common import TestAccountAssetCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@freeze_time('2026-01-01')
@tagged('post_install', '-at_install')
class TestAssetLedger(TestAccountAssetCommon, TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_asset = cls.env['account.asset'].create({
            'name': 'Original Asset',
            'original_value': 12000.0,
            'acquisition_date': '2024-01-01',
            'account_asset_id': cls.company_data['default_account_assets'].id,
        })
        cls.ledger_journal = cls.env['account.journal'].create({
            'name': 'Ledger Miscellaneous Operations',
            'code': 'MISC-t',
            'type': 'general',
            'journal_group_id': cls.env['account.journal.group'].create({
                'name': 'test ledger',
            }).id,
        })
        cls.ledger_model = cls.test_asset.model_id.copy({
            'method_number': 4,
            'journal_id': cls.ledger_journal.id,
            'ledger_depreciation_account_id': cls.company_data['default_account_assets'].asset_depreciation_account_id.copy().id,
            'ledger_expense_account_id': cls.company_data['default_account_assets'].asset_expense_account_id.copy().id,
            'ledger_recovery_account_id': cls.company_data['default_account_assets'].asset_expense_account_id.copy().id,
        })

    def _get_depreciation_ledger_move_values(self, date, depreciation_value, depreciated_value, state):
        return {
            'date': fields.Date.from_string(date),
            'depreciation_value': depreciation_value,
            'asset_depreciated_value': depreciated_value,
            'state': state,
        }

    def _copy_journal_with_new_ledger(self, journal, new_ledger_name):
        new_ledger = journal.journal_group_id.copy({
            'name': new_ledger_name,
        })
        return journal.copy({
            'journal_group_id': new_ledger.id,
        })

    def _create_model(self, base_model=None, **vals):
        return (base_model or self.test_asset.model_id).copy(vals)

    def _create_test_asset(self, name, ledger_model=False, validate=False, **asset_vals):
        asset = self.test_asset.copy({'name': name})
        if asset_vals:
            asset.write(asset_vals)
        if ledger_model:
            asset._create_variants(ledger_model)
        if validate:
            asset.validate()
        return asset

    def _create_ledger_wizard(self, asset, ledger_model, **field_values):
        wizard = self.env['depreciation.ledger.wizard'].create({
            'asset_id': asset.id,
        })
        wizard.depreciation_model_id = ledger_model
        wizard.write(field_values)
        return wizard

    def _assert_has_main_variant_only(self, asset):
        self.assertTrue(asset.main_variant_id, "Asset should have a main variant")
        self.assertEqual(asset.variant_ids, asset.main_variant_id, "Asset should have 1 variant which is the main variant")

    def _get_main_and_ledger_variant(self, asset):
        self.assertEqual(len(asset.variant_ids), 2)
        return asset.main_variant_id, asset.variant_ids - asset.main_variant_id

    def _assert_variant_states(self, asset, expected_states):
        self.assertEqual(set(asset.variant_ids.mapped('state')), set(expected_states))

    def _assert_last_ledger_move_balanced(self, ledger_variant):
        self.assertEqual(
            max(ledger_variant.depreciation_move_ids, key=lambda m: (m.date, m.id)).asset_depreciated_value,
            0,
        )

    def test_variant_created_in_asset_creation(self):
        """ Test that a variant is created while creating an asset and saved as main asset variant
        """
        self._assert_has_main_variant_only(self.test_asset)

    def test_ledger_variant_falls_back_to_the_accounts_of_the_asset(self):
        """ A ledger model that names no accounts of its own, records its entries where the
            main variant does
        """
        bare_model = self.ledger_model.copy({
            'ledger_depreciation_account_id': False,
            'ledger_expense_account_id': False,
        })
        asset = self._create_test_asset('Fallback Accounts Asset', ledger_model=bare_model, validate=True)
        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)
        self.assertEqual(ledger_variant.account_depreciation_id, main_variant.account_depreciation_id)
        self.assertEqual(ledger_variant.account_depreciation_expense_id, main_variant.account_depreciation_expense_id)
        self.assertEqual(
            ledger_variant.recovery_account_id, bare_model.ledger_recovery_account_id,
            "The recovery account has no equivalent on the main variant and is still taken from the model",
        )
        # the board is posted on those accounts
        self._assert_variant_states(asset, {'open'})
        self.assertEqual(
            ledger_variant.depreciation_move_ids.line_ids.account_id,
            main_variant.account_depreciation_id
            | main_variant.account_depreciation_expense_id
            | ledger_variant.recovery_account_id,
        )
        # testing wizard shows the accounts that will be used
        asset = self._create_test_asset('Wizard Fallback Asset', validate=True)
        wizard = self._create_ledger_wizard(asset, bare_model)
        self.assertEqual(wizard.depreciation_account_id, main_variant.account_depreciation_id)
        self.assertEqual(wizard.expense_account_id, main_variant.account_depreciation_expense_id)
        self.assertEqual(wizard.recovery_account_id, bare_model.ledger_recovery_account_id)
        wizard.apply()
        _main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)
        self.assertEqual(ledger_variant.account_depreciation_id, main_variant.account_depreciation_id)
        self.assertEqual(ledger_variant.account_depreciation_expense_id, main_variant.account_depreciation_expense_id)

        # testing a half configured model
        half_configured = self.ledger_model.copy({'ledger_expense_account_id': False})
        asset = self._create_test_asset('Half Configured Asset', ledger_model=half_configured, validate=True)
        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)
        self.assertEqual(ledger_variant.account_depreciation_id, half_configured.ledger_depreciation_account_id)
        self.assertNotEqual(ledger_variant.account_depreciation_id, main_variant.account_depreciation_id)
        self.assertEqual(ledger_variant.account_depreciation_expense_id, main_variant.account_depreciation_expense_id)

    def test_variant_created_from_depreciation_ledger_wizard(self):
        """ Test that asset variants are created from the depreciation ledger wizard
        """
        # Create an asset
        asset = self.test_asset
        asset.validate()
        self._assert_has_main_variant_only(asset)

        # Create variant from an existing depreciation ledger
        new_wizard = self._create_ledger_wizard(asset, self.ledger_model)
        new_wizard.apply()
        self.assertEqual(len(asset.variant_ids), 2, "Asset should have 2 variants after applying the depreciation ledger wizard")
        self.assertEqual(max(asset.variant_ids, key=lambda v: (v.id)).model_id, self.ledger_model)

        # Create variant from a new depreciation ledger
        new_model = self.ledger_model.copy({
            'journal_id': self._copy_journal_with_new_ledger(self.ledger_journal, "Second Ledger").id,
        })
        new_wizard = self._create_ledger_wizard(
            asset,
            new_model,
            depreciation_account_id=self.company_data['default_account_assets'].asset_depreciation_account_id.copy().id,
            expense_account_id=self.company_data['default_account_assets'].asset_expense_account_id.copy().id,
            recovery_account_id=self.company_data['default_account_assets'].asset_expense_account_id.copy().id,
        )
        new_wizard.apply()
        self.assertEqual(len(asset.variant_ids), 3, "Asset should have 3 variants after applying the depreciation ledger wizard with creation")
        new_variant = max(asset.variant_ids, key=lambda v: (v.id))
        self.assertRecordValues(new_variant, [{
            'model_id': new_model.id,
            'account_depreciation_id': new_wizard.depreciation_account_id.id,
            'account_depreciation_expense_id': new_wizard.expense_account_id.id,
            'recovery_account_id': new_wizard.recovery_account_id.id,
        }])

        self._assert_variant_states(asset, {'open'})

    def test_auto_create_asset_from_bill_with_ledgers(self):
        asset_account = self.company_data['default_account_assets'].copy({
            'name': 'Auto Asset Account',
        })
        asset_account.ledger_depreciation_model_ids = self.ledger_model

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [Command.create({
                'name': 'Auto-created asset',
                'quantity': 1.0,
                'price_unit': 12000.0,
                'account_id': asset_account.id,
                'tax_ids': [Command.clear()],
            })],
        })
        bill.action_post()

        asset = bill.invoice_line_ids.asset_ids
        self.assertEqual(len(asset), 1, "Posting the bill should auto-create exactly one asset")
        self.assertEqual(asset.account_asset_id, asset_account)
        self.assertEqual(len(asset.variant_ids), 2, "The auto-created asset should include the configured ledger variant")
        self._assert_variant_states(asset, {'open'})
        self.assertEqual(asset.main_variant_id.model_id, asset_account.depreciation_model_id)
        self.assertEqual((asset.variant_ids - asset.main_variant_id).model_id, self.ledger_model)

        # If the asset account doesn't have a depreciation model set (for main variant)
        # then no asset is created
        asset_account_no_depr = self.company_data['default_account_assets'].copy({
            'name': 'No Asset Account',
            'depreciation_model_id': False,
        })
        self.assertTrue(asset_account.ledger_depreciation_model_ids)
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [Command.create({
                'name': 'Test',
                'quantity': 1.0,
                'price_unit': 12000.0,
                'account_id': asset_account_no_depr.id,
                'tax_ids': [Command.clear()],
            })],
        })
        bill.action_post()
        self.assertFalse(bill.invoice_line_ids.asset_ids)

    def test_duplicate_asset(self):
        """ Test that duplicating an asset while having a 'variant_id' in context (from the old asset)
            correctly sets the new asset's values and doesn't point to the old variant.
        """
        asset = self.test_asset
        # Add depreciation models to create variant asset
        asset._create_variants(self.ledger_model)

        # Ensure asset has a main variant
        self.assertTrue(asset.main_variant_id, "Asset should have a main variant")
        old_variant_id = asset.main_variant_id.id

        # Simulate Context having variant_id of the old asset (as if we are on its form view)
        ctx = {'variant_id': old_variant_id}

        # Ensure the current selected id is not the variant id in the context
        new_asset = asset.with_context(ctx).copy()
        new_asset_with_ctx = new_asset.with_context(ctx)
        self.assertEqual(new_asset_with_ctx.current_selected_variant_id, new_asset_with_ctx.main_variant_id,
                         "New asset should have the current selected variant as the main variant")
        self.assertEqual(new_asset_with_ctx.current_selected_variant_id.asset_id, new_asset,
                         "Selected variant should belong to the new asset")

        # Ensure values copied correctly and no depreciation model or variant ids are copied
        self.assertEqual(new_asset_with_ctx.original_value, 12000)
        self.assertEqual(new_asset_with_ctx.account_asset_id, asset.account_asset_id)
        self.assertEqual(new_asset_with_ctx.model_id, asset.main_variant_id.model_id)
        self.assertFalse(new_asset_with_ctx.depreciation_move_ids)

    def test_deleting_a_main_variant_along_with_its_siblings(self):
        """ Deleting the main variant deletes its asset, which cascades to every variant of
            that asset at the database level. A sibling listed in the same recordset is
            therefore already gone and must not be unlinked a second time.
        """
        asset = self._create_test_asset('Deleted with its siblings', ledger_model=self.ledger_model)
        main = asset.main_variant_id
        secondary = asset.variant_ids - main
        self.assertTrue(secondary, "the asset needs a second variant for this scenario")
        (main + secondary).unlink()
        self.assertFalse(asset.exists())
        self.assertFalse((main + secondary).exists())

        # the order in the recordset does not matter
        other_asset = self._create_test_asset('Deleted in the other order', ledger_model=self.ledger_model)
        other_main = other_asset.main_variant_id
        other_secondary = other_asset.variant_ids - other_main
        (other_secondary + other_main).unlink()
        self.assertFalse(other_asset.exists())
        self.assertFalse((other_main + other_secondary).exists())

        # deleting a secondary variant keeps the asset
        asset = self._create_test_asset('Kept asset', ledger_model=self.ledger_model)
        main = asset.main_variant_id
        secondary = asset.variant_ids - main
        secondary.unlink()
        self.assertTrue(asset.exists())
        self.assertEqual(asset.variant_ids, main)

        # cannot delete a running asset
        asset = self._create_test_asset('Running asset', ledger_model=self.ledger_model, validate=True)
        main = asset.main_variant_id
        secondary = asset.variant_ids - main
        self.assertEqual(secondary.state, 'open')
        with self.assertRaisesRegex(UserError, "You cannot delete an asset variant that is in"):
            (main + secondary).unlink()
        self.assertTrue(asset.exists())
        self.assertEqual(len(asset.variant_ids), 2)

    def test_deleting_a_gross_increase_asset(self):
        """ The main variant of a gross increase is parented, so it is absent from its own
            asset's 'variant_ids': the cascade still removes it and it must not be unlinked
            a second time.
        """
        base = self._create_test_asset('Base of the increase')
        increase = self.env['account.asset'].create({
            'name': 'Gross increase',
            'original_value': 1000.0,
            'acquisition_date': '2024-06-01',
            'account_asset_id': self.company_data['default_account_assets'].id,
            'parent_id': base.main_variant_id.id,
        })
        self.assertTrue(increase.main_variant_id.parent_id, "the increase hangs under the base asset")
        self.assertEqual(increase.variant_ids, increase.main_variant_id)

        increase.main_variant_id.unlink()
        self.assertFalse(increase.exists())

    def test_a_gross_increase_is_managed_like_any_other_asset(self):
        """ The main variant of a gross increase is parented, but it is still a variant of
            its own asset: state transitions have to reach it.
        """
        base = self._create_test_asset('Base of the managed increase')
        increase = self.env['account.asset'].create({
            'name': 'Managed gross increase',
            'original_value': 1000.0,
            'acquisition_date': '2024-06-01',
            'account_asset_id': self.company_data['default_account_assets'].id,
            'parent_id': base.main_variant_id.id,
        })
        self.assertEqual(increase.variant_ids, increase.main_variant_id, "the parented variant belongs to its asset")
        self.assertEqual(increase.variant_count, 1)

        increase.validate()
        self.assertEqual(increase.main_variant_id.state, 'open')

        increase.set_to_cancelled()
        self.assertEqual(increase.main_variant_id.state, 'cancelled', "the transition must not be a no-op")

        increase.set_to_draft()
        self.assertEqual(increase.main_variant_id.state, 'draft')

    def test_archiving_an_asset_checks_every_variant(self):
        """ Archiving flips every variant inactive, since their 'active' is related to the
            asset's: the check has to look past 'active_test' or it sees no variant at all.
        """
        asset = self._create_test_asset('Archived asset', ledger_model=self.ledger_model)
        main = asset.main_variant_id
        secondary = asset.variant_ids - main
        self.assertTrue(secondary, "the asset needs a second variant for this scenario")

        with self.assertRaisesRegex(UserError, "You cannot archive a record that is not closed"), self.cr.savepoint():
            asset.active = False

        main.state = 'close'
        with self.assertRaisesRegex(UserError, "at least one variant that is not closed"), self.cr.savepoint():
            asset.active = False
        self.assertTrue(asset.active, "the asset stays active while a variant is still running")

        secondary.state = 'close'
        asset.active = False
        self.assertFalse(asset.active, "an asset whose variants are all closed can be archived")

    def test_invalid_variant_id_context_falls_back_to_main_variant(self):
        asset = self._create_test_asset('Context Target Asset')
        other_asset = self._create_test_asset('Context Other Asset')
        other_variant = other_asset._create_variants(self.ledger_model)

        asset_with_invalid_ctx = asset.with_context(variant_id=other_variant.id)
        self.assertEqual(
            asset_with_invalid_ctx.current_selected_variant_id,
            asset.main_variant_id,
            "An unrelated variant in context should fall back to the asset's main variant",
        )

    def test_search_current_selected_variant_id_uses_context_variant_and_main_variant_fallback(self):
        asset = self._create_test_asset('Search Target Asset', ledger_model=self.ledger_model)
        other_asset = self._create_test_asset('Search Fallback Asset')
        subvariant = asset.variant_ids - asset.main_variant_id

        assets_with_subvariant_selected = self.env['account.asset'].with_context(variant_id=subvariant.id).search([
            ('current_selected_variant_id', '=', subvariant.id),
        ])
        self.assertIn(asset, assets_with_subvariant_selected)
        self.assertNotIn(other_asset, assets_with_subvariant_selected)

        assets_with_other_main_variant_selected = self.env['account.asset'].with_context(variant_id=subvariant.id).search([
            ('current_selected_variant_id', '=', other_asset.main_variant_id.id),
        ])
        self.assertIn(other_asset, assets_with_other_main_variant_selected)
        self.assertNotIn(asset, assets_with_other_main_variant_selected)

    def test_cannot_validate_subvariant_before_main_variant_is_open(self):
        asset = self._create_test_asset('Blocked Subvariant Asset')
        subvariant = asset._create_variants(self.ledger_model)

        with self.assertRaisesRegex(UserError, "Cannot confirm current asset while main asset is not running"):
            asset.with_context(variant_id=subvariant.id).validate()

        self._assert_variant_states(asset, {'draft'})

    def test_variant_context_cancel_or_reset_only_affects_selected_variant(self):
        asset = self._create_test_asset('Variant Context Asset', ledger_model=self.ledger_model, validate=True)

        main_variant, subvariant = self._get_main_and_ledger_variant(asset)
        main_move_ids = sorted(main_variant.depreciation_move_ids.ids)

        asset.with_context(variant_id=subvariant.id).set_to_cancelled()
        self.assertEqual(main_variant.state, 'open')
        self.assertEqual(subvariant.state, 'cancelled')
        self.assertEqual(sorted(main_variant.depreciation_move_ids.ids), main_move_ids)

        asset.with_context(variant_id=subvariant.id).set_to_draft()
        self.assertEqual(main_variant.state, 'open')
        self.assertEqual(subvariant.state, 'draft')

    def test_account_rejects_two_ledgers_from_same_journal_group(self):
        asset_account = self.company_data['default_account_assets'].copy({
            'name': 'Same Ledger Group Account',
        })
        second_ledger = self.ledger_model.copy({
            'method_number': 6,
            'journal_id': self.ledger_journal.copy().id,
        })

        with self.assertRaisesRegex(UserError, "The same ledger cannot be linked multiple times on the same account"):
            asset_account.write({
                'ledger_depreciation_model_ids': [Command.set((self.ledger_model + second_ledger).ids)],
            })

    def test_variant_board_for_monthly_or_daily_or_degressive_models(self):
        monthly_asset = self._create_test_asset(
            'Monthly Variant Asset',
            acquisition_date='2025-01-01',
            model_id=self._create_model(
                method_period='1',
                method_number=12,
            ),
        )
        monthly_ledger = self._create_model(
            self.ledger_model,
            method_period='1',
            method_number=6,
        )
        monthly_asset._create_variants(monthly_ledger)
        monthly_asset.validate()
        monthly_main, monthly_ledger_variant = self._get_main_and_ledger_variant(monthly_asset)
        self.assertTrue(all(
            move.date == end_of(move.asset_depreciation_beginning_date, 'month')
            for move in monthly_main.depreciation_move_ids
        ))
        self._assert_last_ledger_move_balanced(monthly_ledger_variant)

        daily_asset = self._create_test_asset(
            'Daily Variant Asset',
            acquisition_date='2024-01-15',
            model_id=self._create_model(
                method_number=2,
                prorata_computation_type='daily_computation',
            ),
        )
        daily_ledger = self._create_model(
            self.ledger_model,
            method_number=1,
            prorata_computation_type='daily_computation',
        )
        daily_asset._create_variants(daily_ledger)
        daily_asset.validate()
        daily_main, daily_ledger_variant = self._get_main_and_ledger_variant(daily_asset)
        self.assertEqual(daily_main.depreciation_move_ids.sorted(lambda m: (m.date, m.id))[0].asset_number_days, 352)
        self._assert_last_ledger_move_balanced(daily_ledger_variant)

        degressive_asset = self._create_test_asset(
            'Degressive Variant Asset',
            model_id=self._create_model(
                method='degressive',
                method_number=4,
                method_progress_factor=0.4,
            ),
        )
        degressive_ledger = self._create_model(
            self.ledger_model,
            method='degressive',
            method_number=3,
            method_progress_factor=0.6,
        )
        degressive_asset._create_variants(degressive_ledger)
        degressive_asset.validate()
        _, degressive_ledger_variant = self._get_main_and_ledger_variant(degressive_asset)
        self._assert_last_ledger_move_balanced(degressive_ledger_variant)
        self.assertIn(degressive_ledger.ledger_recovery_account_id, degressive_ledger_variant.depreciation_move_ids.line_ids.account_id)

    def test_multi_ledger_variant_depreciation_board_1(self):
        """ Test depreciation board is created correctly for asset with 2 variants:
            implicit and explicit ledger.
            The ledger (explicit) model duration is less than main (implicit) model
        """
        asset = self._create_test_asset(
            'Original Asset',
            ledger_model=self.ledger_model.copy({'method_number': 3}),
            validate=True,
        )

        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)
        self.assertEqual(len(main_variant.depreciation_move_ids), len(ledger_variant.depreciation_move_ids))
        self.assertEqual(main_variant.book_value, 7200)
        self.assertRecordValues(main_variant.depreciation_move_ids, [
            self._get_depreciation_move_values(date='2024-12-31', depreciation_value=2400, remaining_value=9600, depreciated_value=2400, state='posted'),
            self._get_depreciation_move_values(date='2025-12-31', depreciation_value=2400, remaining_value=7200, depreciated_value=4800, state='posted'),
            self._get_depreciation_move_values(date='2026-12-31', depreciation_value=2400, remaining_value=4800, depreciated_value=7200, state='draft'),
            self._get_depreciation_move_values(date='2027-12-31', depreciation_value=2400, remaining_value=2400, depreciated_value=9600, state='draft'),
            self._get_depreciation_move_values(date='2028-12-31', depreciation_value=2400, remaining_value=0, depreciated_value=12000, state='draft'),
        ])
        self.assertRecordValues(ledger_variant.depreciation_move_ids, [
            self._get_depreciation_ledger_move_values(date='2024-12-31', depreciation_value=1600, depreciated_value=1600, state='posted'),
            self._get_depreciation_ledger_move_values(date='2025-12-31', depreciation_value=1600, depreciated_value=3200, state='posted'),
            self._get_depreciation_ledger_move_values(date='2026-12-31', depreciation_value=1600, depreciated_value=4800, state='draft'),
            self._get_depreciation_ledger_move_values(date='2027-12-31', depreciation_value=-2400, depreciated_value=2400, state='draft'),
            self._get_depreciation_ledger_move_values(date='2028-12-31', depreciation_value=-2400, depreciated_value=0, state='draft'),
        ])

        ledger_depreciation_account = self.ledger_model.ledger_depreciation_account_id
        ledger_expense_account = self.ledger_model.ledger_expense_account_id
        ledger_recovery_account = self.ledger_model.ledger_recovery_account_id
        self.assertRecordValues(
            ledger_variant.depreciation_move_ids.line_ids,
            [
                # Move 1
                {'debit': 0, 'credit': 4000, 'account_id': ledger_depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
                # Move 2
                {'debit': 0, 'credit': 4000, 'account_id': ledger_depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
                # Move 3
                {'debit': 0, 'credit': 4000, 'account_id': ledger_depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
                # Move 4
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_recovery_account.id},
                # Move 5
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_recovery_account.id},
            ]
        )

    def test_multi_ledger_variant_depreciation_board_2(self):
        """ Test depreciation board is created correctly for asset with 2 variants:
            implicit and explicit ledger.
            The ledger (explicit) model duration is more than main (implicit) model
        """
        asset = self._create_test_asset(
            'Original Asset',
            model_id=self._create_model(method_number=3),
            ledger_model=self.ledger_model.copy({'method_number': 5}),
            validate=True,
        )

        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)
        self.assertTrue(len(ledger_variant.depreciation_move_ids) > len(main_variant.depreciation_move_ids))
        self.assertEqual(main_variant.book_value, 4000)
        self.assertRecordValues(main_variant.depreciation_move_ids, [
            self._get_depreciation_move_values(date='2024-12-31', depreciation_value=4000, remaining_value=8000, depreciated_value=4000, state='posted'),
            self._get_depreciation_move_values(date='2025-12-31', depreciation_value=4000, remaining_value=4000, depreciated_value=8000, state='posted'),
            self._get_depreciation_move_values(date='2026-12-31', depreciation_value=4000, remaining_value=0, depreciated_value=12000, state='draft'),
        ])
        self.assertRecordValues(ledger_variant.depreciation_move_ids, [
            self._get_depreciation_ledger_move_values(date='2024-12-31', depreciation_value=-1600, depreciated_value=-1600, state='posted'),
            self._get_depreciation_ledger_move_values(date='2025-12-31', depreciation_value=-1600, depreciated_value=-3200, state='posted'),
            self._get_depreciation_ledger_move_values(date='2026-12-31', depreciation_value=-1600, depreciated_value=-4800, state='draft'),
            self._get_depreciation_ledger_move_values(date='2027-12-31', depreciation_value=2400, depreciated_value=-2400, state='draft'),
            self._get_depreciation_ledger_move_values(date='2028-12-31', depreciation_value=2400, depreciated_value=0, state='draft'),
        ])

        ledger_depreciation_account = self.ledger_model.ledger_depreciation_account_id
        ledger_expense_account = self.ledger_model.ledger_expense_account_id
        self.assertRecordValues(
            ledger_variant.depreciation_move_ids.line_ids,
            [
                # Move 1
                {'debit': 0, 'credit': 2400, 'account_id': ledger_depreciation_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 4000, 'account_id': ledger_expense_account.id},
                # Move 2
                {'debit': 0, 'credit': 2400, 'account_id': ledger_depreciation_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 4000, 'account_id': ledger_expense_account.id},
                # Move 3
                {'debit': 0, 'credit': 2400, 'account_id': ledger_depreciation_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 4000, 'account_id': ledger_expense_account.id},
                # Move 4
                {'debit': 0, 'credit': 2400, 'account_id': ledger_depreciation_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_expense_account.id},
                # Move 5
                {'debit': 0, 'credit': 2400, 'account_id': ledger_depreciation_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_expense_account.id},
            ]
        )

    def test_multi_ledger_variant_depreciation_board_3(self):
        """ Test depreciation board is created correctly for asset with 2 variants:
            both explicit ledger.
        """
        asset = self._create_test_asset(
            'Original Asset',
            acquisition_date='2024-07-01',
            model_id=self._create_model(self.ledger_model, method_number=5),
            ledger_model=self._create_model(
                self.ledger_model,
                method_number=3,
                journal_id=self._copy_journal_with_new_ledger(self.ledger_journal, 'test ledger 3').id,
            ),
            validate=True,
        )

        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)
        self.assertEqual(len(main_variant.depreciation_move_ids), len(ledger_variant.depreciation_move_ids))
        self.assertEqual(main_variant.book_value, 8400)
        self.assertRecordValues(main_variant.depreciation_move_ids, [
            self._get_depreciation_move_values(date='2024-12-31', depreciation_value=1200, remaining_value=10800, depreciated_value=1200, state='posted'),
            self._get_depreciation_move_values(date='2025-12-31', depreciation_value=2400, remaining_value=8400, depreciated_value=3600, state='posted'),
            self._get_depreciation_move_values(date='2026-12-31', depreciation_value=2400, remaining_value=6000, depreciated_value=6000, state='draft'),
            self._get_depreciation_move_values(date='2027-12-31', depreciation_value=2400, remaining_value=3600, depreciated_value=8400, state='draft'),
            self._get_depreciation_move_values(date='2028-12-31', depreciation_value=2400, remaining_value=1200, depreciated_value=10800, state='draft'),
            self._get_depreciation_move_values(date='2029-12-31', depreciation_value=1200, remaining_value=0, depreciated_value=12000, state='draft'),
        ])
        self.assertRecordValues(ledger_variant.depreciation_move_ids, [
            self._get_depreciation_ledger_move_values(date='2024-12-31', depreciation_value=800, depreciated_value=800, state='posted'),
            self._get_depreciation_ledger_move_values(date='2025-12-31', depreciation_value=1600, depreciated_value=2400, state='posted'),
            self._get_depreciation_ledger_move_values(date='2026-12-31', depreciation_value=1600, depreciated_value=4000, state='draft'),
            self._get_depreciation_ledger_move_values(date='2027-12-31', depreciation_value=-400, depreciated_value=3600, state='draft'),
            self._get_depreciation_ledger_move_values(date='2028-12-31', depreciation_value=-2400, depreciated_value=1200, state='draft'),
            self._get_depreciation_ledger_move_values(date='2029-12-31', depreciation_value=-1200, depreciated_value=0, state='draft'),
        ])

        ledger_depreciation_account = self.ledger_model.ledger_depreciation_account_id
        ledger_expense_account = self.ledger_model.ledger_expense_account_id
        ledger_recovery_account = self.ledger_model.ledger_recovery_account_id
        self.assertRecordValues(
            ledger_variant.depreciation_move_ids.line_ids,
            [
                # Move 1
                {'debit': 0, 'credit': 2000, 'account_id': ledger_depreciation_account.id},
                {'debit': 2000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 1200, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 1200, 'account_id': ledger_expense_account.id},
                # Move 2
                {'debit': 0, 'credit': 4000, 'account_id': ledger_depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
                # Move 3
                {'debit': 0, 'credit': 4000, 'account_id': ledger_depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
                # Move 4
                {'debit': 0, 'credit': 2000, 'account_id': ledger_depreciation_account.id},
                {'debit': 2000, 'credit': 0, 'account_id': ledger_expense_account.id},
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
                # Move 5
                {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 2400, 'account_id': ledger_recovery_account.id},
                # Move 6
                {'debit': 1200, 'credit': 0, 'account_id': ledger_depreciation_account.id},
                {'debit': 0, 'credit': 1200, 'account_id': ledger_recovery_account.id},
            ]
        )

    def test_single_ledger_variant_depreciation_board(self):
        """ Test depreciation board is created correctly for asset with 1 variant:
            explicit ledger only
        """
        asset = self.test_asset
        asset.model_id = self.ledger_model.copy({'method_number': 3})
        asset.validate()

        self.assertEqual(len(asset.variant_ids), 1)
        ledger_variant = asset.variant_ids
        self.assertEqual(ledger_variant, asset.main_variant_id)
        self.assertEqual(ledger_variant.book_value, 4000)
        self.assertRecordValues(ledger_variant.depreciation_move_ids, [
            self._get_depreciation_move_values(date='2024-12-31', depreciation_value=4000, remaining_value=8000, depreciated_value=4000, state='posted'),
            self._get_depreciation_move_values(date='2025-12-31', depreciation_value=4000, remaining_value=4000, depreciated_value=8000, state='posted'),
            self._get_depreciation_move_values(date='2026-12-31', depreciation_value=4000, remaining_value=0, depreciated_value=12000, state='draft'),
        ])

        depreciation_account = asset.account_asset_id.asset_depreciation_account_id
        expense_account = asset.account_asset_id.asset_expense_account_id
        self.assertRecordValues(
            ledger_variant.depreciation_move_ids.line_ids,
            [
                # Move 1
                {'debit': 0, 'credit': 4000, 'account_id': depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': expense_account.id},
                # Move 2
                {'debit': 0, 'credit': 4000, 'account_id': depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': expense_account.id},
                # Move 3
                {'debit': 0, 'credit': 4000, 'account_id': depreciation_account.id},
                {'debit': 4000, 'credit': 0, 'account_id': expense_account.id},
            ]
        )

    def test_ledger_variant_closed_on_disposal(self):
        """ Test variants are closed correctly when asset is disposed with 2 variants:
            - implicit ledger with 5 year model
            - explicit ledger with 4 year model
            and dispose after 1.5 years
        """

        disposal_date = fields.Date.to_date('2025-06-30')
        loss_account_id = self.company_data['default_account_expense'].copy()

        asset = self._create_test_asset(
            'Disposed Asset',
            original_value=12000,
            ledger_model=self.ledger_model,
            validate=True,
        )
        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)

        self._assert_variant_states(asset, {'open'})

        # Not possible to dispose ledger variant
        with self.assertRaisesRegex(UserError, "A ledger sub-asset is closed together with its asset. Dispose of the asset instead."):
            self.env['asset.modify'].create({
                'asset_variant_id': ledger_variant.id,
                'modify_action': 'dispose',
                'loss_account_id': loss_account_id.id,
                'date': disposal_date,
            }).sell_dispose()

        disposal_action_view = self.env['asset.modify'].create({
            'asset_variant_id': asset.main_variant_id.id,
            'modify_action': 'dispose',
            'loss_account_id': loss_account_id.id,
            'date': disposal_date,
        }).sell_dispose()

        self._assert_variant_states(asset, {'close'})
        self.assertEqual(ledger_variant.disposal_date, disposal_date)
        # Since main assets disposal move is not posted, therefore the book value is not 0
        self.assertEqual(main_variant.book_value, 8400)
        self.assertEqual(ledger_variant.book_value, 8400)
        self.assertFalse(
            ledger_variant.depreciation_move_ids.filtered(lambda m: m.date > disposal_date),
            "No ledger entry may survive the disposal date",
        )

        main_moves = main_variant.depreciation_move_ids.sorted(lambda m: (m.date, m.id))
        ledger_moves = ledger_variant.depreciation_move_ids.sorted(lambda m: (m.date, m.id))
        self.assertRecordValues(main_moves, [
            self._get_depreciation_move_values(date='2024-12-31', depreciation_value=2400, remaining_value=9600, depreciated_value=2400, state='posted'),
            self._get_depreciation_move_values(date='2025-06-30', depreciation_value=1200, remaining_value=8400, depreciated_value=3600, state='posted'),
            self._get_depreciation_move_values(date='2025-06-30', depreciation_value=8400, remaining_value=0, depreciated_value=12000, state='draft'),
        ])
        self.assertRecordValues(ledger_moves, [
            self._get_depreciation_ledger_move_values(date='2024-12-31', depreciation_value=600, depreciated_value=600, state='posted'),
            # The partial ledger's depreciation and main variant's depreciation (3000/2 - 1200)
            self._get_depreciation_ledger_move_values(date='2025-06-30', depreciation_value=300, depreciated_value=900, state='posted'),
            # Disposal move: flushes the remaining 900 delta. Posted right away.
            self._get_depreciation_ledger_move_values(date='2025-06-30', depreciation_value=-900, depreciated_value=0, state='posted'),
        ])
        self._assert_last_ledger_move_balanced(ledger_variant)

        self.env['account.move'].browse(disposal_action_view['res_id']).action_post()
        self.assertRecordValues(main_moves[-1], [
            self._get_depreciation_move_values(date='2025-06-30', depreciation_value=8400, remaining_value=0, depreciated_value=12000, state='posted'),
        ])
        self.assertEqual(main_variant.book_value, 0)
        self.assertEqual(ledger_variant.book_value, 0)

        ledger_depreciation_account = self.ledger_model.ledger_depreciation_account_id
        ledger_expense_account = self.ledger_model.ledger_expense_account_id
        ledger_recovery_account = self.ledger_model.ledger_recovery_account_id

        self.assertRecordValues(ledger_moves.line_ids, [
            # Move 1
            {'debit': 0, 'credit': 3000, 'account_id': ledger_depreciation_account.id},
            {'debit': 3000, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
            # Move 2
            {'debit': 0, 'credit': 1500, 'account_id': ledger_depreciation_account.id},
            {'debit': 1500, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 1200, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 1200, 'account_id': ledger_expense_account.id},
            # Move 3
            {'debit': 900, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 900, 'account_id': ledger_recovery_account.id},
        ])
        disposal_move = ledger_moves[-1]
        self.assertNotIn(
            ledger_expense_account, disposal_move.line_ids.account_id,
            "The disposal of a ledger variant is not a depreciation: it must not include the expense account",
        )

    def test_ledger_variant_closed_on_sale(self):
        """ Test variants are closed correctly when asset is sold with 2 variants:
            - implicit ledger with 5 year model
            - explicit ledger with 4 year model
            and sale after 4.5 years
        """

        disposal_date = fields.Date.to_date('2025-06-30')
        gain_account_id = self.company_data['default_account_revenue'].copy()

        asset = self._create_test_asset(
            'Disposed Asset',
            original_value=12000,
            acquisition_date='2021-01-01',
            ledger_model=self.ledger_model,
            validate=True,
        )
        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)

        self._assert_variant_states(asset, {'open'})

        # At time of sale: asset book value = 12000 - 12000 * 4.5 / 5 = 1200
        # Selling with a gain of 800
        selling_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {'price_unit': 2000})]
        })

        # Not possible to sell ledger variant
        with self.assertRaisesRegex(UserError, "A ledger sub-asset is closed together with its asset. Dispose of the asset instead."):
            self.env['asset.modify'].create({
                'asset_variant_id': ledger_variant.id,
                'invoice_line_ids': selling_invoice.invoice_line_ids,
                'date': disposal_date,
                'modify_action': 'sell',
                'gain_account_id': gain_account_id.id,
            }).sell_dispose()

        disposal_action_view = self.env['asset.modify'].create({
            'asset_variant_id': main_variant.id,
            'invoice_line_ids': selling_invoice.invoice_line_ids,
            'date': disposal_date,
            'modify_action': 'sell',
            'gain_account_id': gain_account_id.id,
        }).sell_dispose()

        self._assert_variant_states(asset, {'close'})
        self.assertEqual(ledger_variant.disposal_date, disposal_date)
        # Since main assets disposal move is not posted, therefore the book value is not 0
        self.assertEqual(main_variant.book_value, 1200)
        self.assertEqual(ledger_variant.book_value, 1200)
        self.assertFalse(
            ledger_variant.depreciation_move_ids.filtered(lambda m: m.date > disposal_date),
            "No ledger entry may survive the disposal date",
        )

        main_moves = main_variant.depreciation_move_ids.sorted(lambda m: (m.date, m.id))
        ledger_moves = ledger_variant.depreciation_move_ids.sorted(lambda m: (m.date, m.id))
        self.assertRecordValues(main_moves, [
            self._get_depreciation_move_values(date='2021-12-31', depreciation_value=2400, remaining_value=9600, depreciated_value=2400, state='posted'),
            self._get_depreciation_move_values(date='2022-12-31', depreciation_value=2400, remaining_value=7200, depreciated_value=4800, state='posted'),
            self._get_depreciation_move_values(date='2023-12-31', depreciation_value=2400, remaining_value=4800, depreciated_value=7200, state='posted'),
            self._get_depreciation_move_values(date='2024-12-31', depreciation_value=2400, remaining_value=2400, depreciated_value=9600, state='posted'),
            self._get_depreciation_move_values(date='2025-06-30', depreciation_value=1200, remaining_value=1200, depreciated_value=10800, state='posted'),
            self._get_depreciation_move_values(date='2025-06-30', depreciation_value=1200, remaining_value=0, depreciated_value=12000, state='draft'),
        ])
        self.assertRecordValues(ledger_moves, [
            self._get_depreciation_ledger_move_values(date='2021-12-31', depreciation_value=600, depreciated_value=600, state='posted'),
            self._get_depreciation_ledger_move_values(date='2022-12-31', depreciation_value=600, depreciated_value=1200, state='posted'),
            self._get_depreciation_ledger_move_values(date='2023-12-31', depreciation_value=600, depreciated_value=1800, state='posted'),
            self._get_depreciation_ledger_move_values(date='2024-12-31', depreciation_value=600, depreciated_value=2400, state='posted'),
            # The ledger finished depreciating. A recovery move is used to counteract the main move's depreciation.
            self._get_depreciation_ledger_move_values(date='2025-06-30', depreciation_value=-1200, depreciated_value=1200, state='posted'),
            # Disposal move: flushes the remaining 1200 delta. Posted right away.
            self._get_depreciation_ledger_move_values(date='2025-06-30', depreciation_value=-1200, depreciated_value=0, state='posted'),
        ])
        self._assert_last_ledger_move_balanced(ledger_variant)

        self.env['account.move'].browse(disposal_action_view['res_id']).action_post()
        self.assertRecordValues(main_moves[-1], [
            self._get_depreciation_move_values(date='2025-06-30', depreciation_value=1200, remaining_value=0, depreciated_value=12000, state='posted'),
        ])
        self.assertEqual(main_variant.book_value, 0)
        self.assertEqual(ledger_variant.book_value, 0)

        ledger_depreciation_account = self.ledger_model.ledger_depreciation_account_id
        ledger_expense_account = self.ledger_model.ledger_expense_account_id
        ledger_recovery_account = self.ledger_model.ledger_recovery_account_id

        self.assertRecordValues(ledger_moves.line_ids, [
            # Move 1
            {'debit': 0, 'credit': 3000, 'account_id': ledger_depreciation_account.id},
            {'debit': 3000, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
            # Move 2
            {'debit': 0, 'credit': 3000, 'account_id': ledger_depreciation_account.id},
            {'debit': 3000, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
            # Move 3
            {'debit': 0, 'credit': 3000, 'account_id': ledger_depreciation_account.id},
            {'debit': 3000, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
            # Move 4
            {'debit': 0, 'credit': 3000, 'account_id': ledger_depreciation_account.id},
            {'debit': 3000, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
            # Move 5
            {'debit': 1200, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 1200, 'account_id': ledger_recovery_account.id},
            # Move 6 (Disposal move)
            {'debit': 1200, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 1200, 'account_id': ledger_recovery_account.id},
        ])
        disposal_move = ledger_moves[-1]
        self.assertNotIn(
            ledger_expense_account, disposal_move.line_ids.account_id,
            "The disposal of a ledger variant is not a depreciation: it must not include the expense account",
        )

    def test_ledger_variant_closed_on_disposal_at_period_end(self):
        """ Test variants are closed correctly when asset is disposed with 2 variants:
            - implicit ledger with 5 year model
            - explicit ledger with 4 year model
            and dispose exactly after 1 year, while every depreciation move is still draft
        """

        disposal_date = fields.Date.to_date('2025-12-31')
        loss_account_id = self.company_data['default_account_expense'].copy()

        asset = self._create_test_asset(
            'Disposed Asset',
            original_value=12000,
            acquisition_date='2025-01-01',
            ledger_model=self.ledger_model,
            validate=True,
        )
        main_variant, ledger_variant = self._get_main_and_ledger_variant(asset)

        self._assert_variant_states(asset, {'open'})

        self.env['asset.modify'].create({
            'asset_variant_id': main_variant.id,
            'modify_action': 'dispose',
            'loss_account_id': loss_account_id.id,
            'date': disposal_date,
        }).sell_dispose()

        self._assert_variant_states(asset, {'close'})
        self.assertEqual(ledger_variant.disposal_date, disposal_date)
        self.assertEqual(main_variant.book_value, 9600)
        self.assertEqual(ledger_variant.book_value, 9600)
        self.assertFalse(
            ledger_variant.depreciation_move_ids.filtered(lambda m: m.date > disposal_date),
            "No ledger entry may survive the disposal date",
        )

        main_moves = main_variant.depreciation_move_ids.sorted(lambda m: (m.date, m.id))
        ledger_moves = ledger_variant.depreciation_move_ids.sorted(lambda m: (m.date, m.id))
        self.assertRecordValues(main_moves, [
            self._get_depreciation_move_values(date='2025-12-31', depreciation_value=2400, remaining_value=9600, depreciated_value=2400, state='posted'),
            self._get_depreciation_move_values(date='2025-12-31', depreciation_value=9600, remaining_value=0, depreciated_value=12000, state='draft'),
        ])
        self.assertRecordValues(ledger_moves, [
            # A full year of the ledger's own depreciation (3000), countered by the main variant's (2400)
            self._get_depreciation_ledger_move_values(date='2025-12-31', depreciation_value=600, depreciated_value=600, state='posted'),
            # Disposal move: flushes the remaining 600 delta.
            self._get_depreciation_ledger_move_values(date='2025-12-31', depreciation_value=-600, depreciated_value=0, state='posted'),
        ])
        self._assert_last_ledger_move_balanced(ledger_variant)

        asset.variant_ids.depreciation_move_ids.filtered(lambda m: m.state == 'draft').action_post()
        self.assertEqual(main_variant.book_value, 0)
        self.assertEqual(ledger_variant.book_value, 0)

        ledger_depreciation_account = self.ledger_model.ledger_depreciation_account_id
        ledger_expense_account = self.ledger_model.ledger_expense_account_id
        ledger_recovery_account = self.ledger_model.ledger_recovery_account_id

        self.assertRecordValues(ledger_moves.line_ids, [
            # Move 1
            {'debit': 0, 'credit': 3000, 'account_id': ledger_depreciation_account.id},
            {'debit': 3000, 'credit': 0, 'account_id': ledger_expense_account.id},
            {'debit': 2400, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 2400, 'account_id': ledger_expense_account.id},
            # Move 2 (Disposal move)
            {'debit': 600, 'credit': 0, 'account_id': ledger_depreciation_account.id},
            {'debit': 0, 'credit': 600, 'account_id': ledger_recovery_account.id},
        ])
        disposal_move = ledger_moves[-1]
        self.assertNotIn(
            ledger_expense_account, disposal_move.line_ids.account_id,
            "The disposal of a ledger variant is not a depreciation: it must not include the expense account",
        )

    def test_asset_variant_creation_form(self):
        """ Test asset is created with variants in form view
        """
        asset_form = Form(self.test_asset)

        # Values should be set from fixed asset account
        self.assertEqual(asset_form.model_id, self.company_data['default_account_assets'].depreciation_model_id)
        self.assertEqual(asset_form.prorata_computation_type, self.company_data['default_account_assets'].depreciation_model_id.prorata_computation_type)

        # Variants created upon save
        asset = asset_form.save()
        asset._create_variants(self.ledger_model)
        self.assertEqual(len(asset.variant_ids), 2)

        # Form view of second variant and trying to set values of main asset
        variant_form = Form(asset.with_context(variant_id=asset.variant_ids[1].id))
        with self.assertRaises(AssertionError):
            variant_form.original_value = 20000
        with self.assertRaises(AssertionError):
            variant_form.acquisition_date = '2026-01-01'
        with self.assertRaises(AssertionError):
            variant_form.model_id = asset.model_id.copy({'method_number': 7})
        with self.assertRaises(AssertionError):
            variant_form.journal_id = asset.journal_id.copy()

        self.assertEqual(variant_form.original_value, 12000)
        self.assertEqual(variant_form.acquisition_date, '2024-01-01')
        self.assertEqual(variant_form.model_id, self.ledger_model)
        self.assertEqual(variant_form.journal_id, self.ledger_model.journal_id)

    def test_cannot_create_implicit_variant(self):
        """ Test cannot create an implicit variant as a non-main variant
        """
        asset = self.test_asset
        implicit_model = asset.model_id.copy({'method_number': 3})
        with self.assertRaisesRegex(UserError, "An asset cannot have two variants linked to the same ledger"):
            asset._create_variants(implicit_model)

    def test_cannot_create_variants_with_same_ledger(self):
        """ Test cannot create two variants with depreciation models linked to the same ledger
        """
        asset = self.test_asset

        # 3 different models with different journals but same ledger
        implicit_model = self.test_asset.model_id
        explicit_model_1 = self.ledger_model.copy({'method_number': 1, 'journal_id': self.ledger_journal.copy().id})
        explicit_model_2 = self.ledger_model.copy({'method_number': 2, 'journal_id': self.ledger_journal.copy().id})

        asset.model_id = explicit_model_1
        with self.assertRaisesRegex(UserError, "An asset cannot have two variants linked to the same ledger"):
            asset._create_variants(explicit_model_2)

        asset.model_id = implicit_model
        asset._create_variants(explicit_model_1)
        with self.assertRaisesRegex(UserError, "An asset cannot have two variants linked to the same ledger"):
            asset._create_variants(explicit_model_2)

        with self.assertRaisesRegex(UserError, "An asset cannot have two variants linked to the same ledger"):
            asset.model_id = explicit_model_2

    def test_depreciation_schedule_with_multiple_variants(self):
        """ Test depreciation schedule report for multiple assets with multiple variants
        """
        all_assets = self.env['account.asset'].search([])
        all_assets.set_to_cancelled()     # To avoid interference with the test

        model_3_yr_implicit = self.test_asset.model_id.copy({'method_number': 3})
        model_3_yr_explicit = self.ledger_model.copy({'method_number': 3})
        model_5_yr_implicit = self.test_asset.model_id
        model_5_yr_explicit = self.ledger_model.copy({'method_number': 5})

        # Asset 1: Implicit (5 years) & explicit (3 years)
        self._create_test_asset(
            'Asset 1',
            model_id=model_5_yr_implicit,
            ledger_model=model_3_yr_explicit,
            validate=True,
        )

        # Asset 2: Implicit (3 years) & explicit (5 years)
        self._create_test_asset(
            'Asset 2',
            model_id=model_3_yr_implicit,
            ledger_model=model_5_yr_explicit,
            validate=True,
        )

        # Asset 3: Explicit (5 years) & explicit (3 years)
        new_ledger_journal = self._copy_journal_with_new_ledger(self.ledger_journal, 'test ledger 2')
        self._create_test_asset(
            'Asset 3',
            acquisition_date='2024-07-01',
            model_id=model_5_yr_explicit,
            ledger_model=model_3_yr_explicit.copy({'journal_id': new_ledger_journal.id}),
            validate=True,
        )

        # Asset 4: Explicit (3 years) only
        self._create_test_asset('Asset 4', model_id=model_3_yr_explicit).validate()

        expected_values = {
            #    Name                     A/start    A/+  A/-  A/end  Depr/start  Depr/+  Depr/-  Depr/end  Book Value
            ('2024-01-01', '2024-12-31'): [
                ('Depreciation Schedule',       0,  48000,  0,  48000,        0,  14000,  1600,  12400,    35600),
                ('15',                          0,  48000,  0,  48000,        0,  14000,  1600,  12400,    35600),
                ('Asset 1',                     0,  12000,  0,  12000,        0,   4000,     0,   4000,     8000),
                ('Asset 2',                     0,  12000,  0,  12000,        0,   4000,  1600,   2400,     9600),
                ('Asset 4',                     0,  12000,  0,  12000,        0,   4000,     0,   4000,     8000),
                ('Asset 3',                     0,  12000,  0,  12000,        0,   2000,     0,   2000,    10000),
            ],
            ('2025-01-01', '2025-12-31'): [
                ('Depreciation Schedule',   48000,      0,  0,  48000,    12400,  16000,  1600,  26800,    21200),
                ('15',                      48000,      0,  0,  48000,    12400,  16000,  1600,  26800,    21200),
                ('Asset 1',                 12000,      0,  0,  12000,     4000,   4000,     0,   8000,     4000),
                ('Asset 2',                 12000,      0,  0,  12000,     2400,   4000,  1600,   4800,     7200),
                ('Asset 4',                 12000,      0,  0,  12000,     4000,   4000,     0,   8000,     4000),
                ('Asset 3',                 12000,      0,  0,  12000,     2000,   4000,     0,   6000,     6000),
            ],
            ('2026-01-01', '2026-12-31'): [
                ('Depreciation Schedule',   48000,      0,  0,  48000,    26800,  16000,  1600,  41200,     6800),
                ('15',                      48000,      0,  0,  48000,    26800,  16000,  1600,  41200,     6800),
                ('Asset 1',                 12000,      0,  0,  12000,     8000,   4000,     0,  12000,        0),
                ('Asset 2',                 12000,      0,  0,  12000,     4800,   4000,  1600,   7200,     4800),
                ('Asset 4',                 12000,      0,  0,  12000,     8000,   4000,     0,  12000,        0),
                ('Asset 3',                 12000,      0,  0,  12000,     6000,   4000,     0,  10000,     2000),
            ],
            ('2027-01-01', '2027-12-31'): [
                ('Depreciation Schedule',   48000,      0,  0,  48000,    41200,   7200,  2800,  45600,     2400),
                ('15',                      48000,      0,  0,  48000,    41200,   7200,  2800,  45600,     2400),
                ('Asset 1',                 12000,      0,  0,  12000,    12000,   2400,  2400,  12000,        0),
                ('Asset 2',                 12000,      0,  0,  12000,     7200,   2400,     0,   9600,     2400),
                ('Asset 4',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 3',                 12000,      0,  0,  12000,    10000,   2400,   400,  12000,        0),
            ],
            ('2028-01-01', '2028-12-31'): [
                ('Depreciation Schedule',   48000,      0,  0,  48000,    45600,   7200,  4800,  48000,        0),
                ('15',                      48000,      0,  0,  48000,    45600,   7200,  4800,  48000,        0),
                ('Asset 1',                 12000,      0,  0,  12000,    12000,   2400,  2400,  12000,        0),
                ('Asset 2',                 12000,      0,  0,  12000,     9600,   2400,     0,  12000,        0),
                ('Asset 4',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 3',                 12000,      0,  0,  12000,    12000,   2400,  2400,  12000,        0),
            ],
            ('2029-01-01', '2029-12-31'): [
                ('Depreciation Schedule',   48000,      0,  0,  48000,    48000,   1200,  1200,  48000,        0),
                ('15',                      48000,      0,  0,  48000,    48000,   1200,  1200,  48000,        0),
                ('Asset 1',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 2',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 4',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 3',                 12000,      0,  0,  12000,    12000,   1200,  1200,  12000,        0),
            ],
            ('2030-01-01', '2030-12-31'): [
                ('Depreciation Schedule',   48000,      0,  0,  48000,    48000,      0,     0,  48000,        0),
                ('15',                      48000,      0,  0,  48000,    48000,      0,     0,  48000,        0),
                ('Asset 1',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 2',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 4',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
                ('Asset 3',                 12000,      0,  0,  12000,    12000,      0,     0,  12000,        0),
            ],
        }

        all_journals = self.env['account.journal'].search([])
        self.env.company.totals_below_sections = False
        report = self.env.ref('account_asset.assets_report')
        for key, expected_lines in expected_values.items():
            options = self._generate_options(report, key[0], key[1], default_options={'all_entries': True, 'unfold_all': True})
            self._press_journal_filter(options, all_journals)
            self.assertLinesValues(
                report._get_lines(options),
                [0, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                expected_lines,
                options,
            )
