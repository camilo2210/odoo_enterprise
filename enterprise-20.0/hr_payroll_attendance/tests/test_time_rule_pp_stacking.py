# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('-at_install', 'post_install', 'work_entry_pipeline')
class TestTimeRulePpStacking(TransactionCase):
    """Verify that premium pay (pp) frozensets stack correctly across overlapping rules.

    When R2 reclassifies an interval already tagged by R1, the output record must carry
    the union of both rules' pp categories.  This is guaranteed by the alloc_acc
    mechanism: R1 lands in alloc_acc, and _resolve_output_intervals builds pp from
    alloc_acc | {cls_rule}.

    The Saturday attendance is fully excess from the start (schedule=0h on Sat), so
    _apply_output always takes the in-place path: the source attendance itself is
    reclassified and gets category_options_ids set via _get_source_annotation_vals.
    There are no child overtime records; we assert directly on the source.
    """

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

        cls.env['hr.time.rule'].search([]).write({'active': False})

        cls.emp = cls.env['hr.employee'].create({
            'name': 'PP Stack Emp',
            'tz': 'UTC',
            'attendance_based': False,
            'date_version': '2020-01-01',
            'contract_date_start': '2020-01-01',
            'wage': 3500,
        })

        cls.cat_a = cls.env['hr.salary.rule.category'].create({'name': 'Cat A', 'code': 'PPCA'})
        cls.cat_b = cls.env['hr.salary.rule.category'].create({'name': 'Cat B', 'code': 'PPCB'})
        cls.ot_type = cls.env['hr.work.entry.type'].create({'name': 'OT PP', 'code': 'OTPP'})

    def test_overlapping_rules_pp_stacking(self):
        """R1 (allocate-only, pp=CAT_A) tagged by R2 (output WET, pp=CAT_B).

        R2 reclassifies R1's intervals; the in-place updated source attendance must carry
        both CAT_A and CAT_B on category_options_ids — the union of all rules' pp that
        ever classified the interval.
        """
        self.env['hr.time.rule'].create({
            'name': 'R1 Sat Alloc-Only',
            'sequence': 10,
            'apply_monday': False, 'apply_tuesday': False, 'apply_wednesday': False,
            'apply_thursday': False, 'apply_friday': False,
            'apply_saturday': True, 'apply_sunday': False,
            'work_entry_type_id': False,
            'premium_pay_category_ids': [self.cat_a.id],
            'condition_work_entry_type_ids': [self.att_type.id],
        })
        self.env['hr.time.rule'].create({
            'name': 'R2 Sat OT',
            'sequence': 20,
            'apply_monday': False, 'apply_tuesday': False, 'apply_wednesday': False,
            'apply_thursday': False, 'apply_friday': False,
            'apply_saturday': True, 'apply_sunday': False,
            'work_entry_type_id': self.ot_type.id,
            'premium_pay_category_ids': [self.cat_b.id],
            'condition_work_entry_type_ids': [self.att_type.id],
        })
        # 4h Saturday — schedule=0h, so entire attendance is excess from the start.
        # _apply_output takes the in-place path: source is reclassified, no child record.
        att = self.env['hr.attendance'].create({
            'employee_id': self.emp.id,
            'check_in': datetime(2022, 12, 10, 10),   # Saturday
            'check_out': datetime(2022, 12, 10, 14),
        })
        att.invalidate_recordset()

        self.assertEqual(att.work_entry_type_id, self.ot_type,
                         "source attendance reclassified in-place to R2's output WET")
        self.assertIn(self.cat_a, att.sudo().category_options_ids,
                      "R1's pp category must appear (alloc_acc union)")
        self.assertIn(self.cat_b, att.sudo().category_options_ids,
                      "R2's pp category must appear (cls_rule)")

    def test_overlapping_rules_pp_and_alloc_both_stack(self):
        """R1 and R2 both have pp categories AND allocation types; R2 reclassifies R1.

        Both the pp union and the allocation credits must stack independently:
        - source attendance carries CAT_A | CAT_B on category_options_ids
        - allocation for ALLOC_R1 created (R1 in alloc_acc)
        - allocation for ALLOC_R2 created (R2 is cls_rule)
        """
        alloc_r1 = self.env['hr.work.entry.type'].create({
            'name': 'Rest R1', 'code': 'PPRSTR1',
            'requires_allocation': True, 'time_off_selectable': True,
            'leave_validation_type': 'no_validation',
        })
        alloc_r2 = self.env['hr.work.entry.type'].create({
            'name': 'Rest R2', 'code': 'PPRSTR2',
            'requires_allocation': True, 'time_off_selectable': True,
            'leave_validation_type': 'no_validation',
        })
        self.env['hr.time.rule'].create({
            'name': 'R1 Sat Alloc+PP',
            'sequence': 10,
            'apply_monday': False, 'apply_tuesday': False, 'apply_wednesday': False,
            'apply_thursday': False, 'apply_friday': False,
            'apply_saturday': True, 'apply_sunday': False,
            'work_entry_type_id': False,
            'premium_pay_category_ids': [self.cat_a.id],
            'leave_compensation_rate': 0.5,
            'allocation_type_id': alloc_r1.id,
            'condition_work_entry_type_ids': [self.att_type.id],
        })
        self.env['hr.time.rule'].create({
            'name': 'R2 Sat OT+PP+Alloc',
            'sequence': 20,
            'apply_monday': False, 'apply_tuesday': False, 'apply_wednesday': False,
            'apply_thursday': False, 'apply_friday': False,
            'apply_saturday': True, 'apply_sunday': False,
            'work_entry_type_id': self.ot_type.id,
            'premium_pay_category_ids': [self.cat_b.id],
            'leave_compensation_rate': 0.5,
            'allocation_type_id': alloc_r2.id,
            'condition_work_entry_type_ids': [self.att_type.id],
        })
        # 4h Saturday: R1 claims all 4h (alloc_acc), R2 reclassifies all 4h in-place
        att = self.env['hr.attendance'].create({
            'employee_id': self.emp.id,
            'check_in': datetime(2022, 12, 10, 10),   # Saturday
            'check_out': datetime(2022, 12, 10, 14),
        })
        att.invalidate_recordset()

        # pp union on the in-place updated source
        self.assertEqual(att.work_entry_type_id, self.ot_type,
                         "source attendance reclassified in-place to R2's output WET")
        self.assertIn(self.cat_a, att.sudo().category_options_ids,
                      "R1's pp category must be on the output (alloc_acc union)")
        self.assertIn(self.cat_b, att.sudo().category_options_ids,
                      "R2's pp category must be on the output (cls_rule)")

        # allocation stacking: both rules earn credit
        found_r1 = self.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', self.emp.id),
            ('work_entry_type_id', '=', alloc_r1.id),
        ])
        found_r2 = self.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', self.emp.id),
            ('work_entry_type_id', '=', alloc_r2.id),
        ])
        self.assertEqual(len(found_r1), 1,
                         "R1 allocation must be created even though R2 reclassifies its intervals")
        self.assertEqual(len(found_r2), 1, "R2 allocation must be created")
        self.assertAlmostEqual(found_r1.number_of_days, 0.25, places=5,
                               msg="R1: 4h * 50% / 8h/day = 0.25 days")
        self.assertAlmostEqual(found_r2.number_of_days, 0.25, places=5,
                               msg="R2: 4h * 50% / 8h/day = 0.25 days")

    def test_two_pp_only_rules_stack_categories(self):
        """Two true pp-only rules (no WET, no threshold) fire in sequence; pp union appears on the source.

        R1 (no WET, CAT_A) fires: pipeline tuple becomes (att_type, src, rule1, {}).
        R2 (no WET, CAT_B) fires: alloc_acc | {rule1} = {rule1}; tuple becomes
        (att_type, src, rule2, {rule1}).

        In _apply_output, pp-only branch builds:
          pp = rule1._get_pp_frozenset() | rule2._get_pp_frozenset() = {CAT_A.id, CAT_B.id}
        _get_source_annotation_vals writes both to category_options_ids on the source.
        """
        self.env['hr.time.rule'].create({
            'name': 'PP Only R1 (CAT_A)',
            'sequence': 10,
            'working_hours_mode': 'day',
            'apply_monday': False, 'apply_tuesday': False, 'apply_wednesday': False,
            'apply_thursday': False, 'apply_friday': False,
            'apply_saturday': True, 'apply_sunday': False,
            'premium_pay_category_ids': [self.cat_a.id],
            'condition_work_entry_type_ids': [self.att_type.id],
        })
        self.env['hr.time.rule'].create({
            'name': 'PP Only R2 (CAT_B)',
            'sequence': 20,
            'working_hours_mode': 'day',
            'apply_monday': False, 'apply_tuesday': False, 'apply_wednesday': False,
            'apply_thursday': False, 'apply_friday': False,
            'apply_saturday': True, 'apply_sunday': False,
            'premium_pay_category_ids': [self.cat_b.id],
            'condition_work_entry_type_ids': [self.att_type.id],
        })
        att = self.env['hr.attendance'].create({
            'employee_id': self.emp.id,
            'check_in': datetime(2022, 12, 10, 10),   # Saturday
            'check_out': datetime(2022, 12, 10, 14),
        })
        att.invalidate_recordset()

        # pp-only rules do not change the WET
        self.assertEqual(att.work_entry_type_id, self.att_type,
                         "pp-only rules must not reclassify the source WET")
        # both pp categories must appear: CAT_A from rule1 via alloc_acc, CAT_B from rule2
        self.assertIn(self.cat_a, att.sudo().category_options_ids,
                      "R1's pp category must be on the source (alloc_acc union)")
        self.assertIn(self.cat_b, att.sudo().category_options_ids,
                      "R2's pp category must be on the source (cls_rule)")
