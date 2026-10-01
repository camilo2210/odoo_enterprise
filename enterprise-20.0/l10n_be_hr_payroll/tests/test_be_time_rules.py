# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install', 'be_time_rules')
class TestBeTimeRules(TransactionCase):
    """Verify the Belgian data time rules (night CP302, sunday) tag attendance correctly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.belgian_company = cls.env['res.company'].create({
            'name': 'BE Time Rule Test Co',
            'country_id': cls.env.ref('base.be').id,
            'currency_id': cls.env.ref('base.EUR').id,
        })
        cls.env.user.company_ids |= cls.belgian_company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.belgian_company.ids))

        # isolate: deactivate all rules, then re-enable only the two data rules under test
        cls.env['hr.time.rule'].search([]).write({'active': False})
        cls.night_rule = cls.env.ref('l10n_be_hr_payroll.l10n_be_time_rule_night_cp302')
        cls.sunday_rule = cls.env.ref('l10n_be_hr_payroll.l10n_be_time_rule_sunday')
        cls.night_rule.active = True
        cls.sunday_rule.active = True

        cls.att_wet = cls.env.ref('hr_work_entry.be_work_entry_type_attendance')
        cls.night_cat = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT')
        cls.sunday_cat = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN')

        cls.env['l10n.be.joint.committee'].with_context(active_test=False).browse([
            cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_999').id,
            cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
        ]).write({'active': True})

        jc_302 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')
        cls.cp302_employee = cls.env['hr.employee'].sudo().create({
            'name': 'Night Worker (CP302)',
            'company_id': cls.belgian_company.id,
            'tz': 'UTC',
            'date_version': '2020-01-01',
            'contract_date_start': '2020-01-01',
            'wage': 2500.0,
        })
        # write jc directly to the version: the inherited field is a computed+stored field
        # on hr.version whose default compute derives jc from employee_type_id, so passing
        # it via _inherits create gets silently overwritten by a deferred recompute
        cls.cp302_employee.sudo().current_version_id.l10n_be_joint_committee_id = jc_302
        # regular be employee (no cp302 joint committee) for sunday rule + exclusion tests
        cls.be_employee = cls.env['hr.employee'].create({
            'name': 'Regular BE Worker',
            'company_id': cls.belgian_company.id,
            'tz': 'UTC',
            'date_version': '2020-01-01',
            'contract_date_start': '2020-01-01',
            'wage': 2500.0,
        })

    def _make_source_leave(self, employee, date_from, date_to):
        return self.env['hr.leave'].with_context(
            tracking_disable=True,
            mail_activity_automation_skip=True,
            leave_skip_date_check=True,
            leave_fast_create=True,
            leave_skip_state_check=True,
            leave_skip_date_from_to_computation=True,
        ).sudo().create({
            'employee_id': employee.id,
            'work_entry_type_id': self.att_wet.id,
            'date_from': date_from,
            'date_to': date_to,
            'request_date_from': date_from.date(),
            'request_date_to': date_to.date(),
            'state': 'validate',
        })

    def _output_leaves(self, employee):
        return self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('time_rule_id', '!=', False),
        ])

    def test_night_rule_tags_cp302_attendance_in_window(self):
        # mon dec 12 2022 00:00-08:00: 5h in the 00:00-05:00 window, 3h outside
        # pipeline: source reused in-place as 00:00-05:00 output; 05:00-08:00 remainder created
        source = self._make_source_leave(self.cp302_employee, datetime(2022, 12, 12, 0), datetime(2022, 12, 12, 8))
        source.invalidate_recordset()

        output = self._output_leaves(self.cp302_employee)
        self.assertEqual(len(output), 1, "Night rule produces one output leave for the 00:00-05:00 segment")
        # output is the source reused in-place
        self.assertEqual(output, source, "Source record is repurposed as the output, not a new leave")
        self.assertEqual(output.work_entry_type_id, self.att_wet, "Output WET stays attendance")
        self.assertEqual(output.date_from, datetime(2022, 12, 12, 0), "Output starts at source start")
        self.assertEqual(output.date_to, datetime(2022, 12, 12, 5), "Source date_to trimmed to window end")
        self.assertEqual(output.category_options_ids, self.night_cat, "Output carries night premium pay")

        # remainder: 05:00-08:00 is a plain attendance leave, not a time rule output
        all_leaves = self.env['hr.leave'].search([('employee_id', '=', self.cp302_employee.id)])
        remainder = all_leaves - output
        self.assertEqual(len(remainder), 1, "One remainder leave created for the unclassified 05:00-08:00 tail")
        self.assertEqual(remainder.work_entry_type_id, self.att_wet)
        self.assertFalse(remainder.time_rule_id, "Remainder is not a time rule output")
        self.assertEqual(remainder.date_from, datetime(2022, 12, 12, 5))
        self.assertEqual(remainder.date_to, datetime(2022, 12, 12, 8))

    def test_night_rule_skips_non_cp302_employee(self):
        # non-CP302 employee: night rule must not fire, source stays untouched
        source = self._make_source_leave(self.be_employee, datetime(2022, 12, 12, 0), datetime(2022, 12, 12, 8))
        source.invalidate_recordset()

        self.assertFalse(self._output_leaves(self.be_employee),
                         "Night rule must not fire for non-CP302 employees")
        self.assertFalse(source.time_rule_id, "Source is unchanged when no rule fires")
        self.assertEqual(source.date_to, datetime(2022, 12, 12, 8), "Source date_to not trimmed")

    def test_sunday_rule_tags_full_sunday_attendance(self):
        # sun dec 11 2022 09:00-17:00: full span on sunday → entire attendance classified
        # source reused in-place; no remainder (full span is the output)
        source = self._make_source_leave(self.be_employee, datetime(2022, 12, 11, 9), datetime(2022, 12, 11, 17))
        source.invalidate_recordset()

        output = self._output_leaves(self.be_employee)
        self.assertEqual(len(output), 1, "Sunday rule produces one output leave covering the full sunday span")
        self.assertEqual(output, source, "Source record is repurposed as the output")
        self.assertEqual(output.work_entry_type_id, self.att_wet, "Output WET stays attendance")
        self.assertEqual(output.date_from, datetime(2022, 12, 11, 9))
        self.assertEqual(output.date_to, datetime(2022, 12, 11, 17), "Full span is classified; date_to unchanged")
        self.assertEqual(output.category_options_ids, self.sunday_cat, "Output carries Sunday premium pay")
        # no remainder: the entire source span was classified
        all_leaves = self.env['hr.leave'].search([('employee_id', '=', self.be_employee.id)])
        self.assertEqual(all_leaves, output, "No remainder leave created when full span is classified")

    def test_sunday_rule_does_not_fire_on_weekday(self):
        # mon dec 12 2022 09:00-17:00: monday, sunday rule must stay silent
        source = self._make_source_leave(self.be_employee, datetime(2022, 12, 12, 9), datetime(2022, 12, 12, 17))
        source.invalidate_recordset()

        self.assertFalse(self._output_leaves(self.be_employee),
                         "Sunday rule must not fire for attendance on weekdays")
        self.assertFalse(source.time_rule_id, "Source is unchanged when no rule fires")
        self.assertEqual(source.date_to, datetime(2022, 12, 12, 17), "Source date_to not trimmed")

    def test_both_rules_overlap_cp302_sunday_night(self):
        """Both rules fire on CP302 attendance in 00:00-05:00 on Sunday; premium pays accumulate."""
        # sun dec 11 2022 00:00-05:00: inside night window (CP302) AND on sunday
        # night rule: tags 00:00-05:00 with {NIGHT}; sunday rule: accumulates → {NIGHT, SUNDAY}
        # full span classified → source reused in-place, no remainder
        source = self._make_source_leave(self.cp302_employee, datetime(2022, 12, 11, 0), datetime(2022, 12, 11, 5))
        source.invalidate_recordset()

        output = self._output_leaves(self.cp302_employee)
        self.assertEqual(len(output), 1, "Overlapping rules produce one merged output leave")
        self.assertEqual(output, source, "Source record is repurposed as the output")
        self.assertEqual(output.work_entry_type_id, self.att_wet, "Output WET stays attendance")
        self.assertEqual(output.date_from, datetime(2022, 12, 11, 0))
        self.assertEqual(output.date_to, datetime(2022, 12, 11, 5))
        self.assertEqual(output.category_options_ids, self.night_cat | self.sunday_cat,
                         "Output accumulates both night and Sunday premium pay categories")

    def test_sunday_with_partial_night_overlap_splits_output_for_cp302(self):
        # sun dec 11 2022 00:00-09:00
        # night rule (00:00-05:00, CP302): tags 00:00-05:00 with {NIGHT}
        # sunday rule (00:00-24:00, all): accumulates over the full span:
        #   - 00:00-05:00 → {NIGHT, SUNDAY}  (source reused in-place)
        #   - 05:00-09:00 → {SUNDAY}          (new output leave)
        # no remainder: the entire 9h is classified
        source = self._make_source_leave(self.cp302_employee, datetime(2022, 12, 11, 0), datetime(2022, 12, 11, 9))
        source.invalidate_recordset()

        output = self._output_leaves(self.cp302_employee)
        self.assertEqual(len(output), 2,
                         "Pre-dawn and post-dawn segments carry different PP sets -> 2 output leaves")

        by_pp = {frozenset(l.category_options_ids.ids): l for l in output}
        night_sunday = by_pp.get(frozenset([self.night_cat.id, self.sunday_cat.id]))
        sunday_only = by_pp.get(frozenset([self.sunday_cat.id]))

        self.assertTrue(night_sunday, "Pre-dawn segment (00:00-05:00) must carry {NIGHT, SUNDAY}")
        self.assertTrue(sunday_only, "Post-dawn segment (05:00-09:00) must carry {SUNDAY} only")

        # both outputs have the attendance WET
        self.assertEqual(night_sunday.work_entry_type_id, self.att_wet)
        self.assertEqual(sunday_only.work_entry_type_id, self.att_wet)

        # source is reused in-place as the night+sunday segment
        self.assertEqual(night_sunday, source, "Source is repurposed as the pre-dawn output")
        self.assertEqual(night_sunday.date_from, datetime(2022, 12, 11, 0))
        self.assertEqual(night_sunday.date_to, datetime(2022, 12, 11, 5),
                         "Source date_to trimmed to night window end")
        # post-dawn is a new output leave
        self.assertNotEqual(sunday_only, source)
        self.assertEqual(sunday_only.date_from, datetime(2022, 12, 11, 5))
        self.assertEqual(sunday_only.date_to, datetime(2022, 12, 11, 9))
