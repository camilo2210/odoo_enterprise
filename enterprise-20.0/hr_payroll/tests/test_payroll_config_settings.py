# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from psycopg2.errors import UniqueViolation

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'payroll_config_settings')
class TestPayrollConfigSettings(TransactionCase):
    """Generic tests for the versioned ``payroll.config.settings`` model and its
    integration with ``res.company``. Localisation specific behaviour is tested in
    the related ``l10n_**_hr_payroll`` modules.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Config Test Company'})

    def _reset_configs(self, company, *date_versions):
        """Make ``company`` own exactly one config per given effective date.

        A company must always keep at least one configuration, so the requested
        versions are created first and only then is the leftover default dropped.
        """
        new_configs = self.env['payroll.config.settings'].create([
            {'company_id': company.id, 'date_version': dv}
            for dv in date_versions
        ])
        (company.payroll_config_ids - new_configs).unlink()
        return new_configs

    def _create_config(self, date_version):
        return self._reset_configs(self.company, date_version)

    def test_dates_single_version(self):
        """A lone version starts on its effective date and stays open-ended."""
        config = self._create_config(date(2020, 1, 1))
        self.assertEqual(config.date_start, date(2020, 1, 1))
        self.assertFalse(config.date_end, "The only version must have no end date.")

    def test_dates_multiple_versions(self):
        """Each version ends the day before the next one; the latest is open-ended."""
        first, second, third = self._reset_configs(
            self.company, date(2020, 1, 1), date(2021, 6, 1), date(2022, 12, 15))

        self.assertEqual(first.date_start, date(2020, 1, 1))
        self.assertEqual(first.date_end, date(2021, 5, 31))

        self.assertEqual(second.date_start, date(2021, 6, 1))
        self.assertEqual(second.date_end, date(2022, 12, 14))

        self.assertEqual(third.date_start, date(2022, 12, 15))
        self.assertFalse(third.date_end, "The latest version must have no end date.")

    def test_unique_date_version(self):
        """A company cannot have two versions sharing the same effective date."""
        self._create_config(date(2020, 1, 1))
        with mute_logger('odoo.sql_db'), self.assertRaises(UniqueViolation):
            self.env['payroll.config.settings'].create({
                'company_id': self.company.id,
                'date_version': date(2020, 1, 1),
            })

    @freeze_time('2023-07-15')
    def test_copy_data_resets_date_version(self):
        """Copying a version sets its effective date to the first of the current month."""
        config = self._create_config(date(2020, 1, 1))
        copy = config.copy()
        self.assertEqual(copy.date_version, date(2023, 7, 1))

    def test_cannot_delete_last_version(self):
        """The last remaining configuration of a company cannot be deleted."""
        config = self._create_config(date(2020, 1, 1))
        with self.assertRaises(UserError):
            config.unlink()

    def test_can_delete_non_last_version(self):
        """Deleting a version is allowed as long as one remains."""
        first, second = self._reset_configs(
            self.company, date(2020, 1, 1), date(2021, 1, 1))
        first.unlink()
        self.assertEqual(self.company.payroll_config_ids, second)

    @freeze_time('2022-01-01')
    def test_current_payroll_config_id(self):
        """The current config is the latest version effective on or before today."""
        # A future version must not become the current one.
        __, current, __ = self._reset_configs(
            self.company, date(2020, 1, 1), date(2021, 6, 1), date(2023, 1, 1))

        self.company.invalidate_recordset(['current_payroll_config_id'])
        self.assertEqual(self.company.current_payroll_config_id, current)

    @freeze_time('2022-01-01')
    def test_current_payroll_config_id_only_future(self):
        """With only future versions, fall back to the earliest one."""
        earliest, __ = self._reset_configs(
            self.company, date(2023, 1, 1), date(2024, 1, 1))

        self.company.invalidate_recordset(['current_payroll_config_id'])
        self.assertEqual(self.company.current_payroll_config_id, earliest)

    @freeze_time('2022-01-01')
    def test_current_payroll_config_id_multi_company(self):
        """Each company resolves its own current config (regression: no cross-company leak)."""
        other_company = self.env['res.company'].create({'name': 'Other Config Company'})

        config_a, __ = self._reset_configs(
            self.company, date(2021, 1, 1), date(2023, 1, 1))  # second is future for A
        config_b = self._reset_configs(other_company, date(2021, 6, 1))

        companies = self.company + other_company
        companies.invalidate_recordset(['current_payroll_config_id'])
        self.assertEqual(self.company.current_payroll_config_id, config_a)
        self.assertEqual(other_company.current_payroll_config_id, config_b)

    def test_get_payroll_config_for_date(self):
        """``_get_payroll_config`` returns the version effective at the given date."""
        first, second = self._reset_configs(
            self.company, date(2020, 1, 1), date(2021, 6, 1))

        self.assertEqual(self.company._get_payroll_config(date(2020, 6, 1)), first)
        self.assertEqual(self.company._get_payroll_config(date(2021, 6, 1)), second,
            "The boundary date must select the version starting that day.")
        self.assertEqual(self.company._get_payroll_config(date(2025, 1, 1)), second,
            "A date after the last version selects the latest version.")

    def test_get_payroll_config_before_first_version(self):
        """A date before any version falls back to the earliest version."""
        first, __ = self._reset_configs(
            self.company, date(2020, 1, 1), date(2021, 6, 1))
        self.assertEqual(self.company._get_payroll_config(date(2019, 1, 1)), first)

    @freeze_time('2021-09-01')
    def test_get_payroll_config_defaults_to_today(self):
        """Called without a date, the config effective today is returned (regression: stale import default)."""
        __, current, __ = self._reset_configs(
            self.company, date(2020, 1, 1), date(2021, 6, 1), date(2022, 1, 1))
        self.assertEqual(self.company._get_payroll_config(), current)

    def test_create_payroll_config_copies_previous(self):
        """Creating a new version copies the field values of the latest existing one."""
        first = self._create_config(date(2020, 1, 1))
        first.date_start  # ensure stored fields computed
        new_config = self.company.create_payroll_config(date(2022, 1, 1))

        self.assertIn(new_config, self.company.payroll_config_ids)
        self.assertEqual(new_config.company_id, self.company)
        self.assertEqual(new_config.date_version, date(2022, 1, 1))
        self.assertNotEqual(new_config, first)

    def test_company_create_initializes_config(self):
        """Creating a company provisions at least one payroll configuration."""
        company = self.env['res.company'].create({'name': 'Fresh Company'})
        self.assertTrue(company.payroll_config_ids,
            "A new company must always have a payroll configuration.")
