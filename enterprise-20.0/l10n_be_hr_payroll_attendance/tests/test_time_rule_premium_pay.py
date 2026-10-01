from datetime import date, datetime

from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install', 'time_rule_pp_attendance')
class TestTimeRulePPAttendance(TransactionCase):
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
        cls.env.company.attendance_work_entry_type_id = cls.att_type

        cls.overtime_type = cls.env.ref('hr_work_entry.generic_work_entry_type_overtime')

        cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').write({'active': True})

        cls.sunday_cat = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN')
        cls.night_cat = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT')

        cls.env['hr.time.rule'].search([]).write({'active': False})
        # R1: fires when daily badge time exceeds the employee's schedule; assigns sunday PP
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
            'attendance_based': False,
            'date_version': '2020-01-01',
            'contract_date_start': '2020-01-01',
            'wage': 3500,
        })

    def _badge(self, check_in, check_out):
        return self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': check_in,
            'check_out': check_out,
        })

    def _output_atts(self):
        return self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee.id),
            ('time_rule_id', '!=', False),
        ], order='check_in')

    def _work_entry_vals(self, date_from, date_to):
        return self.employee.version_id.generate_work_entries(date_from, date_to)

    def test_output_attendance_carries_pp_from_rule(self):
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))  # Sun 12h -> all OT

        output = self._output_atts()
        self.assertEqual(len(output), 1)
        self.assertEqual(output.category_options_ids, self.sunday_cat,
                         "Output attendance must carry the rule's premium pay categories")

    def test_rule_without_pp_produces_no_premium_pay_on_attendance(self):
        self.time_rule.premium_pay_category_ids = [Command.clear()]
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        output = self._output_atts()
        self.assertEqual(len(output), 1)
        self.assertFalse(output.category_options_ids,
                         "Rule without PP must produce output with no category_options_ids")

    def test_pp_flows_to_work_entry_val(self):
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        vals = self._work_entry_vals(date(2022, 12, 11), date(2022, 12, 11))
        ot_vals = [v for v in vals if v['work_entry_type_id'] == self.overtime_type]
        self.assertEqual(len(ot_vals), 1)
        self.assertEqual(ot_vals[0].get('category_options_ids'), self.sunday_cat,
                         "OT work entry val must carry the sunday premium pay category")

    def test_no_pp_work_entry_val_has_no_premium_pay(self):
        """Work entry val from a no-PP rule has no category_options_ids in the dict."""
        self.time_rule.premium_pay_category_ids = [Command.clear()]
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        vals = self._work_entry_vals(date(2022, 12, 11), date(2022, 12, 11))
        ot_vals = [v for v in vals if v['work_entry_type_id'] == self.overtime_type]
        self.assertEqual(len(ot_vals), 1)
        pp = ot_vals[0].get('category_options_ids', self.env['hr.salary.rule.category'])
        self.assertFalse(pp, "Work entry val must not carry PP when rule has none")

    def test_sequential_r2_accumulates_pp_on_reclassified_segment(self):
        """R2 targets OT from R1 and accumulates PP: first 3h {sunday}, last 9h {sunday+night}."""
        self.env['hr.time.rule'].create({
            'name': 'Night Reclassifier',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 3.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        output = self._output_atts()
        self.assertEqual(len(output), 2,
                         "R2 splits the 12h OT into 3h(sunday) + 9h(sunday+night)")

        by_pp = {frozenset(a.category_options_ids.ids): a for a in output}
        base_ot = by_pp.get(frozenset([self.sunday_cat.id]))
        double_ot = by_pp.get(frozenset([self.sunday_cat.id, self.night_cat.id]))
        self.assertTrue(base_ot, "First 3h (below R2 threshold) must carry only sunday PP")
        self.assertTrue(double_ot, "Last 9h (R2 excess) must carry accumulated sunday+night PP")
        self.assertAlmostEqual(
            (base_ot.check_out - base_ot.check_in).total_seconds() / 3600, 3.0, places=4,
        )
        self.assertAlmostEqual(
            (double_ot.check_out - double_ot.check_in).total_seconds() / 3600, 9.0, places=4,
        )

    def test_different_pp_sets_produce_separate_work_entry_vals(self):
        """Two output attendances with different PP sets are not merged in generate_work_entries.

        Same scenario as the previous test: 3h{sunday} + 9h{sunday+night}
        """
        self.env['hr.time.rule'].create({
            'name': 'Night Reclassifier',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 3.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        vals = self._work_entry_vals(date(2022, 12, 11), date(2022, 12, 11))
        ot_vals = [v for v in vals if v['work_entry_type_id'] == self.overtime_type]
        self.assertEqual(len(ot_vals), 2,
                         "Different PP sets must not be merged into one work entry val")

        pp_sets = {
            frozenset(v.get('category_options_ids', self.env['hr.salary.rule.category']).ids)
            for v in ot_vals
        }
        self.assertIn(frozenset([self.sunday_cat.id]), pp_sets,
                      "First OT val must carry only sunday PP")
        self.assertIn(frozenset([self.sunday_cat.id, self.night_cat.id]), pp_sets,
                      "Second OT val must carry accumulated sunday+night PP")

    def test_no_threshold_r2_accumulates_pp_on_entire_ot(self):
        """No-threshold R2 reclassifies all OT → single output attendance with {sunday+night}.

        R1 produces 12h OT({sunday}) on Sunday.  R2 (no threshold, condition=[OT],
        PP={night}) reclassifies the entire interval: acc_pp={sunday}|{night}.
        Because R2 produces one contiguous interval, _apply_attendance_output creates
        a single output attendance carrying both PPs.
        """
        self.env['hr.time.rule'].create({
            'name': 'Night Reclassifier No Threshold',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        output = self._output_atts()
        self.assertEqual(len(output), 1,
                         "No-threshold R2 reclassifies all 12h OT → one merged output")
        self.assertEqual(
            output.category_options_ids,
            self.sunday_cat | self.night_cat,
            "Single output must carry accumulated PP from both R1 and R2",
        )
        self.assertAlmostEqual(
            (output.check_out - output.check_in).total_seconds() / 3600, 12.0, places=4,
        )

    def test_no_threshold_r2_pp_in_work_entry_val(self):
        """No-threshold R2 scenario: single OT work entry val carries {sunday+night}."""
        self.env['hr.time.rule'].create({
            'name': 'Night Reclassifier No Threshold',
            'sequence': self.time_rule.sequence + 10,
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.overtime_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })
        self._badge(datetime(2022, 12, 11, 8), datetime(2022, 12, 11, 20))

        vals = self._work_entry_vals(date(2022, 12, 11), date(2022, 12, 11))
        ot_vals = [v for v in vals if v['work_entry_type_id'] == self.overtime_type]
        self.assertEqual(len(ot_vals), 1)
        self.assertEqual(
            ot_vals[0].get('category_options_ids'),
            self.sunday_cat | self.night_cat,
            "Merged OT val must carry the fully accumulated PP set",
        )

    def test_timing_window_rules_carry_distinct_pp_per_window(self):
        """Morning and evening timing windows each emit their own PP:
        Mon 06:00-20:00 with two timing rules:
          morning [00:00-08:00] → OT, PP={sunday}  = 2h (06:00-08:00)
          evening [17:00-24:00] → OT, PP={night}   = 3h (17:00-20:00)
        """
        self.time_rule.active = False
        self.env['hr.time.rule'].create({
            'name': 'Morning Window',
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'timing_start': 0.0,
            'timing_stop': 8.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.att_type.id],
            'premium_pay_category_ids': [Command.set([self.sunday_cat.id])],
        })
        self.env['hr.time.rule'].create({
            'name': 'Evening Window',
            'working_hours_mode': 'day',
            'expected_hours': 0.0,
            'timing_start': 17.0,
            'timing_stop': 24.0,
            'work_entry_type_id': self.overtime_type.id,
            'condition_work_entry_type_ids': [self.att_type.id],
            'premium_pay_category_ids': [Command.set([self.night_cat.id])],
        })

        self._badge(datetime(2022, 12, 12, 6), datetime(2022, 12, 12, 20))

        output = self._output_atts()
        self.assertEqual(len(output), 2)

        by_pp = {frozenset(a.category_options_ids.ids): a for a in output}
        morning_out = by_pp.get(frozenset([self.sunday_cat.id]))
        evening_out = by_pp.get(frozenset([self.night_cat.id]))
        self.assertTrue(morning_out, "Morning output must carry the sunday PP category")
        self.assertTrue(evening_out, "Evening output must carry the night PP category")
        self.assertAlmostEqual(
            (morning_out.check_out - morning_out.check_in).total_seconds() / 3600,
            2.0, places=4, msg="Morning window: 06:00-08:00 = 2h",
        )
        self.assertAlmostEqual(
            (evening_out.check_out - evening_out.check_in).total_seconds() / 3600,
            3.0, places=4, msg="Evening window: 17:00-20:00 = 3h",
        )
