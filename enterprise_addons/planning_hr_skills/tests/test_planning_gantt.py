# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.fields import Datetime
from odoo.tests import Form, tagged

from odoo.addons.planning.tests.common import TestCommonPlanning


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningHrSkillsGantt(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()

        with Form(cls.env['hr.skill.type']) as skill_type:
            skill_type.name = 'Languages'
            with skill_type.skill_ids.new() as skill:
                skill.name = 'English'
            with skill_type.skill_level_ids.new() as level:
                level.name = "C1"
                level.level_progress = 80
        cls.skill_type = skill_type.save()

        cls.env['hr.employee.skill'].create({
            'employee_id': cls.employee_bert.id,
            'skill_id': cls.skill_type.skill_ids.id,
            'skill_level_id': cls.skill_type.skill_level_ids.id,
            'skill_type_id': skill_type.id,
        })

    def test_gantt_expand_resource_with_skill_and_no_slots(self):
        """ Test that an employee with a matching searched skill but no planning slots
            is still displayed/expanded in the Gantt view.
        """
        start_date = Datetime.to_datetime('2026-06-01 00:00:00')
        stop_date = Datetime.to_datetime('2026-06-30 23:59:59')

        gantt_domain = [
            ('start_datetime', '<', stop_date),
            ('end_datetime', '>', start_date),
            '|',
            ('resource_ids', '=', False),
            ('employee_skill_ids', 'ilike', 'eng'),
        ]

        gantt_data = self.env['planning.slot'].with_context(
            planning_expand_resource=True
        ).get_gantt_data(
            domain=gantt_domain,
            groupby=['resource_ids'],
            read_specification={'name': {}},
            start_date=start_date,
            stop_date=stop_date,
            scale='month',
        )

        expanded_resource_ids = [
            group['resource_ids'][0]
            for group in gantt_data.get('groups', [])
            if group.get('resource_ids')
        ]

        self.assertIn(
            self.employee_bert.resource_id.id,
            expanded_resource_ids,
            "The resource with the searched skill must be expanded even if they have no planning slots."
        )
