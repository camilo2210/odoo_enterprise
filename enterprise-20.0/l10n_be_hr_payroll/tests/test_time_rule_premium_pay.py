# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install', 'time_rule_premium_pay')
class TestTimeRulePremiumPay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.calendar = cls.env['resource.calendar'].create({
            'name': '40h/week',
            'attendance_ids': [
                (0, 0, {'dayofweek': wd, 'hour_from': h, 'hour_to': h + 4})
                for wd in ['0', '1', '2', '3', '4']
                for h in [8, 13]
            ],
        })
        cls.env.company.resource_calendar_id = cls.calendar

        cls.att_type = cls.env.company._get_default_attendance_work_entry_type()
        cls.overtime_type = cls.env.ref('hr_work_entry.generic_work_entry_type_overtime')

        # the post_install hook archives all BE salary rule categories; activating a JC
        # triggers _activate_related_payroll_records which unarchives categories with no
        # JC link (premium pay categories)
        cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').write({'active': True})

        cls.sunday_cat = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN')
        cls.night_cat = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT')

        cls.env['hr.time.rule'].search([]).write({'active': False})
        cls.time_rule = cls.env['hr.time.rule'].create({
            'name': 'OT Rule',
            'calendar_source': 'employee',
            'quantity_period': 'day',
            'work_entry_type_id': cls.overtime_type.id,
            'condition_work_entry_type_ids': [cls.att_type.id],
            'premium_pay_category_ids': [Command.set([cls.sunday_cat.id])],
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'tz': 'UTC',
            'date_version': '2020-01-01',
            'contract_date_start': '2020-01-01',
            'wage': 3500,
        })

    def _make_source_leave(self, date_from, date_to):
        return self.env['hr.leave'].with_context(
            tracking_disable=True,
            mail_activity_automation_skip=True,
            leave_skip_date_check=True,
            leave_fast_create=True,
            leave_skip_state_check=True,
            leave_skip_date_from_to_computation=True
        ).sudo().create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.att_type.id,
            'date_from': date_from,
            'date_to': date_to,
            'request_date_from': date_from.date(),
            'request_date_to': date_to.date(),
            'state': 'validate',
        })

    def _output_leaves(self):
        return self.env['hr.leave'].search([
            ('employee_id', '=', self.employee.id),
            ('time_rule_id', '!=', False),
        ])

    def test_output_leave_gets_premium_pays_from_rule(self):
        """Output leave receives the premium pay categories set on the firing time rule."""
        self._make_source_leave(datetime(2022, 12, 12, 6), datetime(2022, 12, 12, 20))

        output = self._output_leaves()
        self.assertEqual(len(output), 1)
        self.assertEqual(output.category_options_ids, self.sunday_cat,
                         "Output leave should carry the rule's premium pay categories")

    def test_sequential_chained_rules_accumulate_premium_pays(self):
        # R2 fires on OT produced by R1: top 3h of 6h OT gets both sunday + night PPs
        self.env['hr.time.rule'].create({
            'name': 'Double OT Rule',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 3.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })

        self._make_source_leave(datetime(2022, 12, 12, 6), datetime(2022, 12, 12, 20))

        output = self._output_leaves()
        self.assertEqual(len(output), 2,
                         "R1 produces 6h OT; R2 reclassifies last 3h with extra PP → 2 separate output leaves")

        by_pp = {frozenset(l.category_options_ids.ids): l for l in output}
        base_ot = by_pp.get(frozenset([self.sunday_cat.id]))
        double_ot = by_pp.get(frozenset([self.sunday_cat.id, self.night_cat.id]))
        self.assertTrue(base_ot, "First 3h OT should carry only the sunday premium pay")
        self.assertTrue(double_ot, "Last 3h OT should carry accumulated sunday + night premium pays")
        self.assertAlmostEqual(
            (base_ot.date_to - base_ot.date_from).total_seconds() / 3600,
            3.0, places=5, msg="Base OT: 3h (first 3h of excess)",
        )
        self.assertAlmostEqual(
            (double_ot.date_to - double_ot.date_from).total_seconds() / 3600,
            3.0, places=5, msg="Double OT: 3h (last 3h reclassified by R2 with accumulated PPs)",
        )

    def test_different_premium_pays_prevent_slice_merge(self):
        """Two consecutive excess slices with the same output type but different premium
        pay sets must NOT be merged into one output leave."""
        self.time_rule.active = False
        self.env['hr.time.rule'].create({
            'name': 'Morning OT',
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'timing_start': 0.0,
            'timing_stop': 8.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.att_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        self.env['hr.time.rule'].create({
            'name': 'Evening OT',
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'timing_start': 17.0,
            'timing_stop': 24.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.att_type.id],
            'premium_pay_category_ids': [Command.set([self.sunday_cat.id])],
        })
        # 06:00-20:00: [06:00-08:00]=2h morning (night_cat), [17:00-20:00]=3h evening (sunday_cat)
        self._make_source_leave(datetime(2022, 12, 12, 6), datetime(2022, 12, 12, 20))

        output = self._output_leaves()
        self.assertEqual(len(output), 2,
                         "Different premium pay sets must produce separate output leaves")

        by_premium = {frozenset(l.category_options_ids.ids): l for l in output}
        morning_out = by_premium.get(frozenset([self.night_cat.id]))
        evening_out = by_premium.get(frozenset([self.sunday_cat.id]))
        self.assertTrue(morning_out, "Morning slice should carry the night premium pay category")
        self.assertTrue(evening_out, "Evening slice should carry the sunday premium pay category")
        self.assertAlmostEqual(
            (morning_out.date_to - morning_out.date_from).total_seconds() / 3600,
            2.0, places=5, msg="Morning excess: 06:00-08:00 = 2h",
        )
        self.assertAlmostEqual(
            (evening_out.date_to - evening_out.date_from).total_seconds() / 3600,
            3.0, places=5, msg="Evening excess: 17:00-20:00 = 3h",
        )

    def test_no_threshold_r2_reclassifies_all_ot_producing_single_merged_leave(self):
        """A no-threshold R2 targeting all OT produced by R1 reclassifies the entire
        excess with accumulated PPs, yielding exactly one merged output leave."""
        self.env['hr.time.rule'].create({
            'name': 'Night Reclassifier',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        # 14h leave on Mon Dec 12: R1 produces 6h OT(14:00-20:00) with sunday PP
        # R2 no-threshold reclassifies all 6h OT → accumulated pp={sunday, night}
        self._make_source_leave(datetime(2022, 12, 12, 6), datetime(2022, 12, 12, 20))

        output = self._output_leaves()
        self.assertEqual(len(output), 1,
                         "R2 no-threshold reclassifies all OT → one merged output leave")
        self.assertEqual(
            output.category_options_ids,
            self.sunday_cat | self.night_cat,
            "Single output leave must carry accumulated PPs from both R1 and R2",
        )
        self.assertAlmostEqual(
            (output.date_to - output.date_from).total_seconds() / 3600,
            6.0, places=5, msg="All 6h of OT reclassified by R2",
        )

    def test_sequential_night_window_splits_sunday_ot_into_two_leaves(self):
        # R2: no threshold, night window 00:00-06:00, targets OT, adds night PP
        self.env['hr.time.rule'].create({
            'name': 'Night Window',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'timing_start': 0.0,
            'timing_stop': 6.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        # Sunday Dec 11 2022, 04:00-10:00 (6h):
        # - no schedule on Sunday → R1 classifies all 6h as OT with sunday PP
        # - R2 night window [00:00-06:00]: clips OT to [04:00-06:00] → 2h with sunday+night PP
        # - OT remainder [06:00-10:00]: 4h stays with sunday PP only
        self._make_source_leave(datetime(2022, 12, 11, 4), datetime(2022, 12, 11, 10))

        output = self._output_leaves()
        self.assertEqual(len(output), 2,
                         "Night window reclassifies pre-dawn OT → 2 output leaves with different PP sets")

        by_pp = {frozenset(l.category_options_ids.ids): l for l in output}
        night_part = by_pp.get(frozenset([self.sunday_cat.id, self.night_cat.id]))
        day_part = by_pp.get(frozenset([self.sunday_cat.id]))
        self.assertTrue(night_part, "Pre-dawn OT (04:00-06:00) must carry sunday + night PPs")
        self.assertTrue(day_part, "Post-dawn OT (06:00-10:00) must carry only sunday PP")
        self.assertAlmostEqual(
            (night_part.date_to - night_part.date_from).total_seconds() / 3600,
            2.0, places=5, msg="Night portion: 04:00-06:00 = 2h",
        )
        self.assertAlmostEqual(
            (day_part.date_to - day_part.date_from).total_seconds() / 3600,
            4.0, places=5, msg="Day portion: 06:00-10:00 = 4h",
        )
