# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import fields
from odoo.tests import new_test_user

from odoo.addons.planning.tests.common import TestCommonPlanning


class TestPlanningFieldServiceCommon(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('planning.group_planning_manager')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Partner',
        })
        cls.george_user = new_test_user(cls.env, login='george', name='George', groups='planning.group_planning_user')
        cls.marcel_user = new_test_user(cls.env, login='marcel', name='Marcel', groups='planning.group_planning_user')
        cls.henri_user = new_test_user(cls.env, login='henri', groups='planning.group_planning_user')
        cls.current_employee, cls.marcel_employee, cls.henri_employee, cls.george_employee = cls.env['hr.employee'].create([
            {
                'name': 'Current User',
                'user_id': cls.env.user.id,
                'tz': 'UTC',
            },
            {
                'name': 'Marcel',
                'user_id': cls.marcel_user.id,
                'tz': 'UTC',
            },
            {
                'name': 'Henri',
                'user_id': cls.henri_user.id,
                'tz': 'UTC',
            },
            {
                'name': 'George',
                'user_id': cls.george_user.id,
                'tz': 'UTC',
            }
        ])
        cls.intervention, cls.second_intervention = cls.env['planning.slot'].create([
            {
                'name': 'Field Service',
                'partner_id': cls.partner.id,
                'resource_ids': cls.george_employee.resource_id.ids,
                'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
                'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
                'state': '2_published',
            },
            {
                'name': 'Field Service 2',
                'partner_id': cls.partner.id,
                'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
                'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
                'state': '2_published',
            },
        ])

        cls.base_user = new_test_user(cls.env, 'Base user', groups='base.group_user')
        cls.planning_user = new_test_user(cls.env, 'Planning user', groups='planning.group_planning_user')
        cls.planning_manager = new_test_user(cls.env, 'Planning admin', groups='planning.group_planning_manager')
        cls.portal_user = new_test_user(cls.env, 'Portal user', groups='base.group_portal')
