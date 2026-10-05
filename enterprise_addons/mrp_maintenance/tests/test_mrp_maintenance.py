# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime, timedelta
from freezegun import freeze_time

from odoo.tests import tagged, common, Form


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestMrpMaintenance(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Relative models
        cls.ResUsers = cls.env['res.users']
        cls.equipment = cls.env['maintenance.equipment']
        cls.workcenter = cls.env['mrp.workcenter']

        # User references
        cls.main_company = cls.env.ref('base.main_company')
        calendar = cls.env['resource.calendar'].create({
            'name': 'Main Company Calendar',
            'company_id': cls.main_company.id,
        })
        cls.main_company.resource_calendar_id = calendar
        cls.main_company.tz = 'UTC'
        cls.technician_user_id = cls.env.ref('base.user_root')
        cls.maintenance_team_id = cls.env.ref('maintenance.equipment_team_maintenance')
        cls.stage_id = cls.env.ref('maintenance.stage_0').id
        cls.category_id = cls.env['maintenance.equipment.category'].create({
            'name': 'Monitors - Test',
            'technician_user_id': cls.env.ref('base.user_admin').id,
            'color': 3,
        })

        # Create user
        cls.user = cls.ResUsers.create({
            'name': "employee",
            'company_id': cls.main_company.id,
            'login': "employee",
            'email': "employee@yourcompany.example.com",
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]
        })

        # Create user with extra rights
        cls.manager = cls.ResUsers.create({
            'name': "Equipment Manager",
            'company_id': cls.main_company.id,
            'login': "manager",
            'email': "eqmanager@yourcompany.example.com",
            'group_ids': [(6, 0, [cls.env.ref('maintenance.group_equipment_manager').id])]
        })

        # Create workcenter
        cls.workcenter_id = cls.env['mrp.workcenter'].create({
            'name': 'Workcenter 01',
        })

        cls.product = cls.env['product.product'].create({'name': 'Test Product'})
        cls.bom = cls.env['mrp.bom'].create({'product_tmpl_id': cls.product.product_tmpl_id.id})
        cls.operation = cls.env['mrp.routing.workcenter'].create({
            'name': 'Test Operation',
            'workcenter_id': cls.workcenter_id.id,
            'bom_id': cls.bom.id,
        })

    # Create method for create a maintenance request
    def _create_request(self, name, schedule_date, equipment_id, maintenance_type):
        values = {
            'name': name,
            'schedule_date': schedule_date,
            'user_ids': [self.user.id],
            'owner_user_id': self.user.id,
            'equipment_id': equipment_id.id,
            'maintenance_type': maintenance_type,
            'stage_id': self.stage_id,
            'maintenance_team_id': self.maintenance_team_id.id,
        }
        return self.env['maintenance.request'].create(values)

    def _create_workcenter_request(self, name, schedule_date, workcenter_id, maintenance_type, **kwargs):
        """ Create and return a workcenter maintenance request """
        values = {
            'name': name,
            'schedule_date': schedule_date,
            'user_ids': [self.technician_user_id.id],
            'maintenance_for': 'workcenter',
            'workcenter_id': workcenter_id.id,
            'maintenance_type': maintenance_type,
            'maintenance_team_id': self.maintenance_team_id.id,
            'stage_id': self.stage_id,
            **kwargs,
        }
        return self.env['maintenance.request'].create(values)

    def test_00_mrp_maintenance(self):

        """ In order to check Next preventive maintenance date"""
        """
        ex:  equipment      =     Acer Laptop
             effective_date = 25-04-2018
             period         = 5

            preventive maintenance date = effective date + period
                30-04-2018              = 25-04-2018     + 5 days

            create maintenance request
                schedule_date  =  effective date + period
                30-04-2018    = 25-04-2018      + 5 days

            close maintenance request and calculate preventive maintenance date
            close_date = 05-05-2018

            preventive maintenance date = close_date + period
                10-05-2018              = 05-05-2018 + 5day
        """

        # Required for `assign_date` to be visible in the view
        with self.debug_mode():
            # Create a new equipment
            equipment_form = Form(self.equipment)
            equipment_form.name = 'Acer Laptop'
            equipment_form.maintenance_team_id = self.maintenance_team_id
            equipment_form.category_id = self.category_id
            equipment_form.technician_user_id = self.technician_user_id
            equipment_form.assign_date = time.strftime('%Y-%m-%d')
            equipment_form.serial_no = 'MT/127/18291015'
            equipment_form.expected_mtbf = 2
            equipment_form.effective_date = (datetime.now().date() + timedelta(days=5)).strftime("%Y-%m-%d")
            equipment_01 = equipment_form.save()

        # Check that equipment is created or not
        self.assertTrue(equipment_01, 'Equipment not created')

        # Create a maintenance request
        maintenance_request_01 = self._create_request(name='Display not working', schedule_date=datetime.now() + timedelta(days=10), equipment_id=equipment_01, maintenance_type="preventive")

        # check that maintenance_request is created or not
        self.assertTrue(maintenance_request_01, 'Maintenance Request not created')

        # check maintenance scheduled date.
        self.assertEqual(maintenance_request_01.schedule_date.date(), datetime.now().date() + timedelta(days=10), 'maintenance schedule_date is wrong')

        # Updating maintenance to Done state and its close date
        maintenance_request_01.state = 'done'
        maintenance_request_01.close_date = datetime.now().date() + timedelta(days=15)

        # Create another request which would be in maintenance todo stage
        maintenance_request_02 = self._create_request(name='Display not working', schedule_date=datetime.now() + timedelta(days=25), equipment_id=equipment_01, maintenance_type="preventive")

        # check that maintenance_request is created or not
        self.assertTrue(maintenance_request_02, 'Maintenance Request not created')

    def test_01_mrp_maintenance(self):
        """ In order to check MTBF,MTTR,estimated next failure and estimated
            latest failure equipment requests.
        """

        # Required for `assign_date` to be visible in the view
        with self.debug_mode():
            # Create a new equipment
            equipment_form = Form(self.equipment)
            equipment_form.name = 'Acer Laptop'
            equipment_form.maintenance_team_id = self.maintenance_team_id
            equipment_form.category_id = self.category_id
            equipment_form.technician_user_id = self.technician_user_id
            equipment_form.assign_date = time.strftime('%Y-%m-%d')
            equipment_form.serial_no = 'MT/127/18291015'
            equipment_form.expected_mtbf = 2
            equipment_form.effective_date = '2017-04-13'
            equipment_01 = equipment_form.save()

        # Check that equipment is created or not
        self.assertTrue(equipment_01, 'Equipment not created')

        # Create maintenance requests

        # Maintenance Request          Scheduled Date
        #  1)                          2017-05-03
        #  2)                          2017-05-23
        #  3)                          2017-06-11

        maintenance_request_01 = self._create_request(name='Some keys are not working', schedule_date=datetime(2017, 5, 3), equipment_id=equipment_01, maintenance_type="corrective")
        maintenance_request_02 = self._create_request(name='Touchpad not working', schedule_date=datetime(2017, 5, 23), equipment_id=equipment_01, maintenance_type="corrective")
        maintenance_request_03 = self._create_request(name='Battery drains fast', schedule_date=datetime(2017, 6, 11), equipment_id=equipment_01, maintenance_type="corrective")

        # check that maintenance_request is created or not
        self.assertTrue(maintenance_request_01, 'Maintenance Request not created')
        self.assertTrue(maintenance_request_02, 'Maintenance Request not created')
        self.assertTrue(maintenance_request_03, 'Maintenance Request not created')

        # Request  Scheduled Date  Close Date  diff_days
        #  1)      2017-05-03      2017-05-13     10
        #  2)      2017-05-23      2017-05-28      5
        #  3)      2017-06-11      2017-06-11      0

        # MTTR = Day used to handle maintenance request / No of request
        #   5  =            (10+5+0)15                  /    3

        #  MTBF = Gap in days of between effective date and last request / No of request
        #   19  = (2017-06-11 - 2017-04-13) 59                          /       3

        # estimated next failure = latest failure date + MTBF
        # 2017-06-30 00:00:00    = 2017-06-11           + 19

        # maintenance_request_01 mark as done and write close_date.
        maintenance_request_01.state = 'done'
        maintenance_request_01.close_date = datetime(2017, 5, 3).date() + timedelta(days=10)
        self.assertEqual(maintenance_request_01.close_date, datetime(2017, 5, 13).date(), 'Wrong close date on maintenance request.')

        # maintenance_request_02 mark as done and write close_date.
        maintenance_request_02.state = 'done'
        maintenance_request_02.close_date = datetime(2017, 5, 23).date() + timedelta(days=5)
        self.assertEqual(maintenance_request_02.close_date, datetime(2017, 5, 28).date(), 'Wrong close date on maintenance request.')

        # maintenance_request_03 mark as done and write close_date.
        maintenance_request_03.state = 'done'
        maintenance_request_03.close_date = maintenance_request_03.schedule_end.date()
        self.assertEqual(maintenance_request_03.close_date, datetime(2017, 6, 11).date(), 'Wrong close date on maintenance request.')

        # Check MTTR = Day used to handle maintenance request / No of request (15 / 3)
        self.assertEqual(equipment_01.mttr, 5, 'Maintenance Equipment MTTR(Mean Time To Repair) should be 5 days')

        # Check MTBF = Gap in days of between effective date and last request / No of request
        self.assertEqual(equipment_01.mtbf, 19, 'Maintenance Equipment MTBF(Mean Time Between Failure) should be 19 days')

        # Check calculation of latest failure date (should be 11-06-2017)
        latest_failure_date = equipment_01.latest_failure_date
        self.assertEqual(maintenance_request_03.schedule_date, datetime(2017, 6, 11), 'Wrong schedule_date on maintenance request.')
        self.assertEqual(latest_failure_date, maintenance_request_03.schedule_date.date(), 'Wrong latest_failure_date on maintenance request.')

        # Check calculation of estimated next failure (should be 30-06-2017)
        # Step-1: latest failure date + MTBF
        estimated_next_failure = equipment_01.latest_failure_date + timedelta(days=equipment_01.mtbf)
        self.assertEqual(estimated_next_failure, datetime(2017, 6, 30).date(), 'Wrong latest_failure_date on maintenance request.')

    def test_01_mrp_maintenance_workcenter(self):  # adapted from test_01_mrp_maintenance (working on equipment)
        # Required for `assign_date` to be visible in the view
        with self.debug_mode():
            # Create a new workcenter
            workcenter_form = Form(self.workcenter, view='mrp_maintenance.mrp_workcenter_view_form_inherit_maintenance')
            workcenter_form.name = 'WorkCenter'
            workcenter_form.maintenance_team_id = self.maintenance_team_id
            workcenter_form.technician_user_id = self.technician_user_id
            workcenter_form.expected_mtbf = 2
            workcenter_form.effective_date = '2017-04-13'
            workcenter = workcenter_form.save()

        # Check that workcenter is createdworkcenter
        self.assertTrue(workcenter, 'Equipment not created')

        # Create maintenance requests

        # Maintenance Request          Scheduled Date
        #  1)                          2017-05-03
        #  2)                          2017-05-23
        #  3)                          2017-06-11

        maintenance_request_1 = self._create_workcenter_request(name='Some keys are not working', schedule_date=datetime(2017, 5, 3).date(), workcenter_id=workcenter, maintenance_type="corrective")
        maintenance_request_2 = self._create_workcenter_request(name='Touchpad not working', schedule_date=datetime(2017, 5, 23).date(), workcenter_id=workcenter, maintenance_type="corrective")
        maintenance_request_3 = self._create_workcenter_request(name='Battery drains fast', schedule_date=datetime(2017, 6, 11).date(), workcenter_id=workcenter, maintenance_type="corrective")

        # check that maintenance_requests are created or not
        self.assertTrue(maintenance_request_1, 'Maintenance Request not created')
        self.assertTrue(maintenance_request_2, 'Maintenance Request not created')
        self.assertTrue(maintenance_request_3, 'Maintenance Request not created')

        # Request  Scheduled Date  Close Date  diff_days
        #  1)      2017-05-03    2017-05-13     10
        #  2)      2017-05-23    2017-05-28      5
        #  3)      2017-06-11    2017-06-11      0

        # MTTR = Day used to handle maintenance request / No of request
        #   5  =            (10+5+0)15                  /    3

        #  MTBF = Gap in days of between effective date and last request / No of request
        #   19  = (2017-06-11 - 2017-04-13) 59                          /       3

        # estimated next failure = latest failure date + MTBF
        # 2017-06-30 00:00:00    = 2017-06-11           + 19

        # maintenance_request_1 mark as done and write close_date.
        maintenance_request_1.state = 'done'
        maintenance_request_1.close_date = datetime(2017, 5, 3).date() + timedelta(days=10)
        self.assertEqual(maintenance_request_1.close_date, datetime(2017, 5, 13).date(), 'Wrong close date on maintenance request.')

        # maintenance_request_2 mark as done and write close_date.
        maintenance_request_2.state = 'done'
        maintenance_request_2.close_date = datetime(2017, 5, 23).date() + timedelta(days=5)
        self.assertEqual(maintenance_request_2.close_date, datetime(2017, 5, 28).date(), 'Wrong close date on maintenance request.')

        # maintenance_request_3 mark as done and write close_date.
        maintenance_request_3.state = 'done'
        maintenance_request_3.close_date = maintenance_request_3.schedule_end.date()
        self.assertEqual(maintenance_request_3.close_date, datetime(2017, 6, 11).date(), 'Wrong close date on maintenance request.')

        # Check MTTR = Day used to handle maintenance request / No of request (15 / 3)
        self.assertEqual(workcenter.mttr, 5, 'Maintenance Equipment MTTR(Mean Time To Repair) should be 5 days')

        # Check MTBF = Gap in days of between effective date and last request / No of request
        self.assertEqual(workcenter.mtbf, 19, 'Maintenance Equipment MTBF(Mean Time Between Failure) should be 19 days')

        # Check calculation of latest failure date (should be 11-06-2017)
        latest_failure_date = workcenter.latest_failure_date
        self.assertEqual(maintenance_request_3.schedule_date, datetime(2017, 6, 11), 'Wrong schedule_date on maintenance request.')
        self.assertEqual(latest_failure_date, maintenance_request_3.schedule_date.date(), 'Wrong latest_failure_date on maintenance request.')

        # Check calculation of estimated next failure (should be 30-06-2017)
        # Step-1: latest failure date + MTBF
        estimated_next_failure = workcenter.latest_failure_date + timedelta(days=workcenter.mtbf)
        self.assertEqual(estimated_next_failure, datetime(2017, 6, 30).date(), 'Wrong latest_failure_date on maintenance request.')

    def test_workcenter_unavailability(self):
        # Required for `assign_date` to be visible in the view
        self.env.user.group_ids += self.env.ref('mrp.group_mrp_routings')
        with self.debug_mode():
            # Create a new equipment
            equipment_form = Form(self.equipment)
            equipment_form.name = 'Screwdriver'
            equipment_form.maintenance_team_id = self.maintenance_team_id
            equipment_form.category_id = self.category_id
            equipment_form.technician_user_id = self.technician_user_id
            equipment_form.assign_date = time.strftime('%Y-%m-%d')
            equipment_form.serial_no = 'MT/127/18291015'
            equipment_form.expected_mtbf = 2
            equipment_form.effective_date = datetime.now().date() + timedelta(days=5)
            equipment = equipment_form.save()

        maintenance_request_01 = self._create_request(name='Does not turn', schedule_date=datetime(2017, 5, 3, 8, microsecond=500), equipment_id=equipment, maintenance_type="corrective")
        maintenance_request_01.write({"schedule_end": datetime(2017, 5, 3, 10, microsecond=500), "workcenter_id": self.workcenter_id.id})
        start_datetime = datetime(2017, 5, 3, 7)
        maintenance_request_01.flush_recordset()
        intervals_by_workcenter = self.env["mrp.workorder"]._gantt_unavailability(
            'workcenter_id',
            self.workcenter_id.id,
            start_datetime,
            start_datetime + timedelta(hours=4),
            scale=1
        )
        intervals = intervals_by_workcenter[self.workcenter_id.id]
        # We will have two unavailabilities for the requested timeframe:
        #  - From 7 to 8 -> outside of working hours (according to calendar)
        #  - From 8:500 to 10:500 -> scheduled maintenance
        self.assertEqual(len(intervals), 2)
        self.assertListEqual(
            intervals, [
                {'start': datetime(2017, 5, 3, 7, 0), 'stop': datetime(2017, 5, 3, 8, 0)},
                {'start': datetime(2017, 5, 3, 8, 0, 0, 500), 'stop': datetime(2017, 5, 3, 10, 0, 0, 500)}
            ]
        )

    def test_workcenter_unavailability_ignores_invalid_maintenance_intervals(self):
        self.env.user.group_ids += self.env.ref('mrp.group_mrp_routings')
        with self.debug_mode():
            equipment_form = Form(self.equipment)
            equipment_form.name = 'Broken Screwdriver'
            equipment_form.maintenance_team_id = self.maintenance_team_id
            equipment_form.category_id = self.category_id
            equipment_form.technician_user_id = self.technician_user_id
            equipment_form.assign_date = time.strftime('%Y-%m-%d')
            equipment_form.serial_no = 'MT/127/18291016'
            equipment_form.expected_mtbf = 2
            equipment_form.effective_date = datetime.now().date() + timedelta(days=5)
            equipment = equipment_form.save()

        maintenance_request = self._create_request(
            name='Incomplete interval',
            schedule_date=datetime(2017, 5, 3, 8, microsecond=500),
            equipment_id=equipment,
            maintenance_type="corrective",
        )
        maintenance_request.write({
            "schedule_end": datetime(2017, 5, 3, 10, microsecond=500),
            "workcenter_id": self.workcenter_id.id,
        })
        maintenance_request.flush_recordset()
        self.env.cr.execute(
            "UPDATE maintenance_request SET schedule_date = NULL WHERE id = %s",
            [maintenance_request.id],
        )
        start_datetime = datetime(2017, 5, 3, 7)

        intervals_by_workcenter = self.env["mrp.workorder"]._gantt_unavailability(
            'workcenter_id',
            self.workcenter_id.id,
            start_datetime,
            start_datetime + timedelta(hours=4),
            scale=1
        )

        self.assertListEqual(
            intervals_by_workcenter[self.workcenter_id.id],
            [{'start': datetime(2017, 5, 3, 7, 0), 'stop': datetime(2017, 5, 3, 8, 0)}],
        )

    @freeze_time("2025-10-30 7:00:00")
    def test_workcenter_unavailability_due_to_workorders(self):
        self.env.user.tz = 'UTC'
        mo = self.env['mrp.production'].create({
            'bom_id': self.bom.id,
            'date_start': datetime(2025, 10, 30, 9),
            'date_finished': datetime(2025, 10, 30, 10),
        })
        mo.action_confirm()
        mo.button_plan(as_soon_as_possible=False)
        start_datetime = datetime.now()
        self.env.invalidate_all()

        intervals_by_workcenter = self.env["maintenance.request"]._gantt_unavailability(
            'workcenter_id',
            self.workcenter_id.id,
            start_datetime,
            start_datetime + timedelta(hours=3),  # Get intervals until after all done
            scale=1
        )

        self.assertListEqual(
            intervals_by_workcenter[self.workcenter_id.id], [
                {'start': start_datetime, 'stop': start_datetime + timedelta(hours=1)},  # Holiday until 8AM
                {'start': datetime(2025, 10, 30, 9), 'stop': datetime(2025, 10, 30, 10)}  # Workorder should block
            ]
        )

    def test_maintenance_team_id_compute(self):
        """ Ensure that the maintenance request does not update its maintenance_team_id
        when changing to a workcenter that does not have a maintenance_team_id.
        """

        workcenter_without_team = self.env['mrp.workcenter'].create({
            'name': 'Workcenter No Team',
        })

        request = self._create_workcenter_request(
            name='Unexpected shutdowns',
            schedule_date=datetime(2018, 4, 5),
            workcenter_id=workcenter_without_team,
            maintenance_type="corrective"
        )
        request.write({'workcenter_id': self.workcenter_id.id})

        self.assertEqual(
            request.maintenance_team_id.id,
            self.maintenance_team_id.id,
            "Maintenance team should remain unchanged when workcenter has no maintenance_team_id."
        )

    @freeze_time("2025-05-21 11:00:00")
    def test_maintenance_block_workcenter(self):
        """
        Validate that maintenance requests can create resource leaves as long as they do not
        conflict with existing workorder intervals, regardless of working hours (unlike workorder scheduling).
        Also verifies that recurring maintenance requests are properly rescheduled after any overlapping
        manufacturing orders have been completed.
        """
        mo = self.env['mrp.production'].create({'bom_id': self.bom.id, 'date_start': datetime.now()})  # 11:00 AM - 12:00 PM
        mo.action_confirm()
        mo.button_plan()
        wo_finished_date = mo.workorder_ids[0].date_finished

        # Create a preventive MR scheduled for one day before today (past), from 07:00 to 18:00.
        schedule_date = datetime(2025, 5, 20, 7, 0, 0)
        mr = self._create_workcenter_request(
            name="Preventive Maintenance (Block Workcenter)",
            workcenter_id=self.workcenter_id,
            maintenance_type='preventive',
            schedule_date=schedule_date,
            schedule_end=datetime(2025, 5, 20, 18, 0, 0),
            recurring_maintenance=True,
            repeat_unit='day',
            repeat_interval=1,
            repeat_until=schedule_date + timedelta(weeks=1),
            recurring_leaves_count=2,
            block_workcenter=True,
        )
        # Ensure the MR is allowed to span non-working hours (e.g., 07:00-08:00, 13:00-14:00)
        # and that leave creation in the past is permitted without blocking the user.
        self.assertEqual(len(mr.leave_ids), 3)  # 1 for today + 2 recurring leaves
        self.assertRecordValues(mr.leave_ids, [
            {'date_from': datetime(2025, 5, 20, 7, 0, 0), 'date_to': datetime(2025, 5, 20, 18, 0, 0)},
            {'date_from': wo_finished_date, 'date_to': wo_finished_date + timedelta(hours=11)},
            {'date_from': datetime(2025, 5, 22, 7, 0, 0), 'date_to': datetime(2025, 5, 22, 18, 0, 0)},
        ])

        mr.state = 'done'
        next_mr = self.env['maintenance.request'].search([('id', '!=', mr.id), ('name', '=', mr.name)])

        # Confirm that the next MR is scheduled after the MO has finished
        self.assertEqual(next_mr.schedule_date, wo_finished_date,
            "Next preventive maintenance should be scheduled after the MO's end.")
