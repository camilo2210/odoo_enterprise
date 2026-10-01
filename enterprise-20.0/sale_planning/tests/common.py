# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.addons.planning.tests.common import TestCommonPlanning

class TestCommonSalePlanning(TestCommonPlanning):

    @classmethod
    def setUpEmployees(cls):
        super().setUpEmployees()
        cls.employee_wout = cls.env['hr.employee'].create({
            'name': 'Wout',
            'work_email': 'wout@a.be',
            'tz': 'Europe/Brussels',
        })
        cls.env.cr.execute("UPDATE hr_employee SET create_date=%s WHERE id=%s",
                           ('2021-01-01 00:00:00', cls.employee_wout.id))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        calendar_joseph = cls.env['resource.calendar'].create({
            'name': 'Calendar 1',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 9, 'hour_to': 13}),
                (0, 0, {'dayofweek': '3', 'hour_from': 14, 'hour_to': 18}),
            ]
        })
        calendar_bert = cls.env['resource.calendar'].create({
            'name': 'Calendar 2',
            'hours_per_day': 4,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
            ],
        })
        calendar = cls.env['resource.calendar'].create({
            'name': 'Classic 40h/week',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17})
            ]
        })
        cls.env.user.company_id.resource_calendar_id = calendar
        cls.employee_joseph.resource_calendar_id = calendar_joseph
        cls.employee_bert.resource_calendar_id = calendar_bert
        cls.planning_role_junior = cls.env['planning.role'].create({
            'name': 'Junior Developer'
        })

        cls.planning_partner = cls.env['res.partner'].create({
            'name': 'Customer Credee'
        })
        cls.plannable_product = cls.env['product.product'].create({
            'name': 'Home Help',
            'type': 'service',
            'planning_enabled': True,
            'planning_role_id': cls.planning_role_junior.id
        })
        cls.plannable_so = cls.env['sale.order'].create({
            'partner_id': cls.planning_partner.id,
        })
        cls.plannable_sol = cls.env['sale.order.line'].create({
            'order_id': cls.plannable_so.id,
            'product_id': cls.plannable_product.id,
            'product_uom_qty': 10,
        })
