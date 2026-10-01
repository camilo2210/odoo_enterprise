# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from odoo.addons.account_asset.tests.common import TestAccountAssetCommon


@tagged('post_install', '-at_install')
class TestDepreciationModel(TestAccountAssetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Model = cls.env['account.depreciation.model']
        cls.Journal = cls.env['account.journal']
        company_data_2 = cls.setup_other_company(name="Depreciation Model Company")
        cls.company_a = cls.company_data['company']
        cls.company_b = company_data_2['company']
        cls.journal_a = cls.company_data['default_journal_misc']
        cls.journal_b = company_data_2['default_journal_misc']
        cls.branch = cls.env['res.company'].create({
            'name': "Depreciation Model Branch",
            'country_id': cls.company_a.country_id.id,
            'parent_id': cls.company_a.id,
        })
        cls.env.user.company_ids |= cls.company_b | cls.branch
        cls.recovery_account = cls.company_data['default_account_revenue']

    def _create_model(self, method_number, context=None, **values):
        """ Each model needs its own configuration: identical ones are rejected by the unique index,
            hence the durations that no other model of the database uses.
        """
        return self.Model.with_context(**(context or {})).create({
            'method': 'linear',
            'method_number': method_number,
            'method_period': '12',
            **values,
        })

    def _usable_by(self, journal, company):
        return bool(journal.filtered_domain(self.Journal._check_company_domain(company)))

    def test_name_generation_and_custom_flag(self):
        """ The generated name tells identical configurations apart with the journal, and is only
            flagged as custom once a user actually types one.
        """
        shared = self._create_model(31)
        self.assertEqual(shared.name, "31 Year")
        self.assertFalse(shared.is_name_custom)

        # same configuration, restricted to a company: the journal now has to disambiguate it
        with Form(self.Model) as form:
            form.method_number = 31
            form.company_id = self.company_a
            form.journal_id = self.journal_a
            self.assertEqual(form.name, f"31 Year ({self.journal_a.name})")
        restricted = form.save()
        self.assertEqual(restricted.name, f"31 Year ({self.journal_a.name})")
        self.assertFalse(restricted.is_name_custom)

        # a name the user types is kept, and survives a configuration change
        with Form(restricted) as form:
            form.name = "Company A, 31 years"
        self.assertTrue(restricted.is_name_custom)
        with Form(restricted) as form:
            form.method_number = 30
        self.assertEqual(restricted.name, "Company A, 31 years")

        # emptying it hands the name back to the compute
        with Form(restricted) as form:
            form.name = ""
        self.assertFalse(restricted.is_name_custom)
        self.assertEqual(restricted.name, "30 Year")

    def test_journal_is_stored_per_company(self):
        """ Each company sets and reads its own journal on a model shared by all of them. """
        model = self._create_model(32)

        self.assertEqual(model.with_company(self.company_a).journal_id, self.journal_a)
        self.assertEqual(model.with_company(self.company_b).journal_id, self.journal_b)
        self.assertEqual(model._get_journal(self.company_a), self.journal_a)
        self.assertEqual(model._get_journal(self.company_b), self.journal_b)

        # a company without a value of its own falls back to a journal it may use
        model.with_company(self.company_b).journal_id = False
        self.assertFalse(model.with_company(self.company_b).journal_id)
        self.assertTrue(self._usable_by(model._get_journal(self.company_b), self.company_b))
        self.assertEqual(model.with_company(self.company_a).journal_id, self.journal_a, "company A is untouched")

    def test_journal_with_branch_companies(self):
        """ A branch inherits the journal its parent company configured, until it sets its own. """
        # the high sequence keeps this journal out of the way of a plain search, so that the branch
        # can only reach it by inheriting the configuration of the model
        parent_journal = self.journal_a.copy({'name': "Parent Asset Journal", 'code': 'PASSJ', 'sequence': 99})
        model = self._create_model(33, company_id=self.company_a.id, journal_id=parent_journal.id)

        self.assertFalse(model.with_company(self.branch).journal_id, "the branch has no journal of its own")
        self.assertEqual(
            model._get_journal(self.branch), parent_journal,
            "a branch posts to the journal its parent company configured on the model",
        )

        # a branch setting its own journal overrides the inherited one, and only for itself
        branch_journal = self.journal_a.copy({
            'name': "Branch Journal",
            'code': 'BRJ',
            'company_id': self.branch.id,
        })
        model.with_company(self.branch).journal_id = branch_journal
        self.assertEqual(model._get_journal(self.branch), branch_journal)
        self.assertEqual(model._get_journal(self.company_a), parent_journal, "the parent keeps its own journal")

        # writing from the branch must not turn the inherited journal into a branch override
        inherited = self._create_model(39, company_id=self.company_a.id, journal_id=parent_journal.id)
        inherited.with_company(self.branch).write({'company_id': self.company_a.id})
        self.assertFalse(inherited.with_company(self.branch).journal_id, "the branch must keep inheriting")
        self.assertEqual(inherited._get_journal(self.branch), parent_journal)

    def test_restricting_to_a_company_keeps_the_other_values(self):
        """ Restricting a model makes the journals of the other companies unreachable:
            they are inert, and come back if the model is shared again.
        """
        model = self._create_model(34)
        model.with_company(self.company_a).journal_id = self.journal_a
        model.with_company(self.company_b).journal_id = self.journal_b

        model.with_company(self.company_a).company_id = self.company_a
        self.assertEqual(model.with_company(self.company_a).journal_id, self.journal_a)
        self.assertEqual(model.with_company(self.company_b).journal_id, self.journal_b)

        model.company_id = False
        self.assertEqual(model.with_company(self.company_a).journal_id, self.journal_a)
        self.assertEqual(model.with_company(self.company_b).journal_id, self.journal_b)

    def test_journal_computed_when_the_company_changes(self):
        """ 'journal_id' depends on 'company_id', so restricting a model without a journal gives it
            one the company can use.
        """
        model = self._create_model(35).with_company(self.company_a)
        model.journal_id = False

        model.company_id = self.company_a
        self.assertTrue(self._usable_by(model.journal_id, self.company_a))

    def test_locked_model_can_be_shared_with_all_companies(self):
        """ A company-specific model with assets can be shared to all companies (i.e. remove company_id)
            without any restrictions. Once shared to all companies, it can't be company-specific again.
        """
        model = self._create_model(43, company_id=self.company_a.id)
        asset = self.env['account.asset'].with_company(self.company_a).create({
            'name': "Locking Asset",
            'account_asset_id': self.company_data['default_account_assets'].id,
            'acquisition_date': '2024-01-01',
            'original_value': 12000.0,
            'company_id': self.company_a.id,
            'model_id': model.id,
        })
        asset.validate()
        self.assertTrue(model.has_locking_assets)

        # Cannot update company_id with another field
        with self.assertRaisesRegex(UserError, "Cannot update a depreciation model"):
            model.write({'company_id': False, 'method_number': 47})

        # Can update model to be shared to all companies
        model.company_id = False
        self.assertFalse(model.company_id, "The model should now be available to every company")
        self.assertTrue(model.has_locking_assets)
        # Once shared to all companies, the journal_id sets a journal for every company
        self.assertEqual(model.with_company(self.company_a).journal_id, self.journal_a)
        self.assertEqual(model.with_company(self.company_b).journal_id, self.journal_b)

        # Cannot make it company-specific again
        with self.assertRaisesRegex(UserError, "Cannot update a depreciation model"):
            model.company_id = self.company_a

    def test_model_created_in_ledger_context(self):
        """ A model created from a ledger field ('ledger_journal_only' in the context) only accepts
            a journal linked to a ledger, and defaults to the first one available.
        """
        first_ledger, second_ledger = self.Journal.create([{
            'name': f"Ledger Miscellaneous {index}",
            'code': f'LEDG{index}',
            'type': 'general',
            'sequence': sequence,
            'company_id': self.company_a.id,
            'journal_group_id': self.env['account.journal.group'].create({'name': f"test ledger {index}"}).id,
        } for index, sequence in ((1, 10), (2, 11))])

        model = self._create_model(40, context={'ledger_journal_only': True}, ledger_recovery_account_id=self.recovery_account.id)
        self.assertEqual(model.journal_id, first_ledger, "a plain journal may not be used in this context")

        # the ledgers already used elsewhere are excluded from the candidates
        other_model = self._create_model(41, context={
            'ledger_journal_only': True,
            'excluded_ledger_group_ids': first_ledger.journal_group_id.ids,
        }, ledger_recovery_account_id=self.recovery_account.id)
        self.assertEqual(other_model.journal_id, second_ledger)

        # a journal given explicitly still has to be linked to a ledger
        with self.assertRaisesRegex(ValidationError, "A journal with a ledger is required"):
            self._create_model(42, context={'ledger_journal_only': True}, journal_id=self.journal_a.id)

    def test_is_ledger_journal_follows_the_active_company(self):
        """ 'is_ledger_journal' is computed from a company-dependent field, so it is evaluated for
            the active company rather than shared between them.
        """
        ledger_journal = self.Journal.create({
            'name': "Ledger Miscellaneous",
            'code': 'LEDG',
            'type': 'general',
            'company_id': self.company_a.id,
            'journal_group_id': self.env['account.journal.group'].create({'name': "test ledger"}).id,
        })
        model = self._create_model(36)
        model.with_company(self.company_a).write({
            'journal_id': ledger_journal.id,
            'ledger_recovery_account_id': self.recovery_account.id,
        })
        model.with_company(self.company_b).journal_id = self.journal_b

        self.assertTrue(model.with_company(self.company_a).is_ledger_journal)
        self.assertFalse(model.with_company(self.company_b).is_ledger_journal)

    def test_ledger_journal_requires_a_recovery_account(self):
        """ Models using a ledger journal need a recovery account set.
            The check is company-dependent so companies won't affect each other.
        """
        ledger_journal = self.Journal.create({
            'name': "Ledger Miscellaneous",
            'code': 'LEDGR',
            'type': 'general',
            'company_id': self.company_a.id,
            'journal_group_id': self.env['account.journal.group'].create({'name': "test ledger"}).id,
        })

        # a plain journal does not need one
        model = self._create_model(43, journal_id=self.journal_a.id)
        self.assertFalse(model.ledger_recovery_account_id)

        with self.assertRaisesRegex(ValidationError, "A Recovery Account is required"):
            model.with_company(self.company_a).journal_id = ledger_journal

        model.with_company(self.company_a).write({
            'journal_id': ledger_journal.id,
            'ledger_recovery_account_id': self.recovery_account.id,
        })
        self.assertTrue(model.with_company(self.company_a).is_ledger_journal)

        # the account cannot be removed while the ledger journal is set
        with self.assertRaisesRegex(ValidationError, "A Recovery Account is required"):
            model.with_company(self.company_a).ledger_recovery_account_id = False

        # both fields are company-dependent: the other company keeps its plain journal and
        # is not asked for an account of its own
        model.with_company(self.company_b).journal_id = self.journal_b
        self.assertFalse(model.with_company(self.company_b).ledger_recovery_account_id)

        # creating a model straight on a ledger journal is checked the same way
        with self.assertRaisesRegex(ValidationError, "A Recovery Account is required"):
            self._create_model(44, journal_id=ledger_journal.id)

    def test_journals_of_other_companies_are_not_reachable(self):
        """ 'check_company' constrains the journal to the company setting it. """
        model = self._create_model(38)
        with self.assertRaises(UserError):
            model.with_company(self.company_a).journal_id = self.journal_b

    def test_get_correct_duration_from_rate(self):
        """ A rate whose inverse falls just short of a round figure is correctly handled
            to return the shortest inverse representation to obtain the same rate
        """

        # Rate mode
        for rate, expected_duration in [
            (2.78, 36),    # 1 / 2.78% = 35.97 ≈ 36, because 1 / 36 = 2.78%
            (4.17, 24),    # 1 / 4.17% = 23.98 ≈ 24, because 1 / 24 = 4.17%
            (33.33, 3),
            (50.0, 2),
            (100.0, 1),
            (22.22, 4.5),
            # when no shorter duration inverts back to the inverse of rate rounded to 2 decimals
            (15, 6.67),
            (6.66, 15.02),
        ]:
            with self.subTest(rate=rate):
                model = self.env['account.depreciation.model'].create({
                    'method': 'linear',
                    'method_mode': 'rate',
                    'method_rate': rate / 100,
                    'method_period': '12',
                    'method_number': 1 / rate,   # to bypass constraint
                })
                duration = model._get_rounded_duration()
                self.assertEqual(duration, expected_duration)
                rate_from_inverse = round(100 / duration, 2)
                duration_from_rate = round(100 / rate, 2)
                self.assertTrue(rate_from_inverse == rate or duration_from_rate == expected_duration)

        # Other modes are unaffected (only rounded)
        for method_number, method, expected_method_number in [
            (3.456, 'linear', 3.46),
            (35.9712, 'degressive', 35.97),
        ]:
            with self.subTest(method_number=method_number, method=method):
                model = self.env['account.depreciation.model'].create({
                    'method': method,
                    'method_number': method_number,
                })
                self.assertEqual(model._get_rounded_duration(), expected_method_number)
