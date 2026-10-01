# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command
from odoo.tests import tagged, Form
from odoo.tests.common import TransactionCase


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHrAppraisal(TransactionCase):
    """ Test used to check that when doing appraisal creation."""

    @classmethod
    def setUpClass(cls):
        super(TestHrAppraisal, cls).setUpClass()
        cls.HrEmployee = cls.env['hr.employee']
        cls.HrAppraisal = cls.env['hr.appraisal']
        cls.main_company = cls.env.ref('base.main_company')

        cls.dep_rd = cls.env['hr.department'].create({'name': 'RD Test'})
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Manager User',
            'login': 'manager_user',
            'password': 'manager_user',
            'email': 'demo@demo.com',
            'partner_id': cls.env['res.partner'].create({'name': 'Manager Partner'}).id,
        })
        cls.manager = cls.env['hr.employee'].create({
            'name': 'Manager Test',
            'department_id': cls.dep_rd.id,
            'user_id': cls.manager_user.id,
        })

        cls.job = cls.env['hr.job'].create({'name': 'Developer Test', 'department_id': cls.dep_rd.id})
        cls.colleague = cls.env['hr.employee'].create({'name': 'Colleague Test', 'department_id': cls.dep_rd.id})

        group = cls.env.ref('hr_appraisal.group_hr_appraisal_user').id
        cls.user = cls.env['res.users'].create({
            'name': 'Michael Hawkins',
            'login': 'test',
            'group_ids': [(6, 0, [group])],
            'notification_type': 'email',
        })

        cls.env.company.appraisal_plan = True
        cls.env['ir.config_parameter'].sudo().set_int("hr_appraisal.appraisal_create_in_advance_days", 8)
        cls.duration_after_recruitment = 6
        cls.duration_first_appraisal = 9
        cls.duration_next_appraisal = 12
        cls.env.company.write({
            'duration_after_recruitment': cls.duration_after_recruitment,
            'duration_first_appraisal': cls.duration_first_appraisal,
            'duration_next_appraisal': cls.duration_next_appraisal,
        })
        cls.appraisal_rating = cls.env['hr.appraisal.note'].create({'name': 'Exceeds expectations'})
        cls.employee_feedback = Markup("<span>Employee Feedback</span>")
        cls.manager_feedback = Markup("<span>Manager Feedback</span>")

        with freeze_time(date.today() + relativedelta(months=-6)):
            cls.hr_employee = cls.HrEmployee.create(dict(
                name="Michael Hawkins",
                user_id=cls.user.id,
                department_id=cls.dep_rd.id,
                parent_id=cls.manager.id,
                job_id=cls.job.id,
                work_phone="+3281813700",
                work_email='michael@odoo.com',
            ))
            cls.hr_employee.write({'work_location_id': [(0, 0, {'name': "Grand-Rosière"})]})

    def test_hr_appraisal(self):
        with freeze_time(datetime.combine(date.today() + relativedelta(months=6), time(8, 0))):
            # I run the scheduler
            self.env['res.company']._run_employee_appraisal_plans()  # cronjob

            # I check whether new appraisal is created for above employee or not
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertTrue(appraisals, "Appraisal not created")

            # I start the appraisal process by click on "Start Appraisal" button.
            appraisals.action_confirm()

            # I check that state is "Appraisal Sent".
            self.assertEqual(appraisals.state, '2_pending', "appraisal should be 'Appraisal Sent' state")

            # A final rating is needed before closing the appraisal
            appraisals.assessment_note = self.appraisal_rating
            # I close this Apprisal
            appraisals.action_done()
            # I check that state of Appraisal is done.
            self.assertEqual(appraisals.state, '3_done', "Appraisal should be in done state")

    def test_01_appraisal_next_appraisal_date(self):
        """
            An employee has just started working.
            Check that next_appraisal_date is set properly.
            Also, When there is ongoing appraisal for an employee,
            it means that there is no appraisal plan yet.
            Thus, next_appraisal_date should be empty.
        """
        with freeze_time(date.today() - relativedelta(months=6)):
            months = self.hr_employee.company_id.duration_after_recruitment
            upcoming_appraisal_date = date.today() + relativedelta(months=months)

            self.assertEqual(self.hr_employee.next_appraisal_date, upcoming_appraisal_date, 'next_appraisal_date is not set properly for an employee that has just started')

            # create appraisal manually
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today() + relativedelta(months=1),
                'state': '1_new'
            })
            self.assertEqual(self.hr_employee.next_appraisal_date, False, 'There is an ongoing appraisal for an employee, next_appraisal_date should be empty.')

    def test_appraisal_next_appraisal_date_uppcoming_appraisal(self):
        """
        Check that next_appraisal_date is correct and that indeed,
        appraisal plan generates appraisal at that time.
        """

        with freeze_time(date.today() - relativedelta(months=6)):
            self.hr_employee.last_ongoing_appraisal_date = date.today()

            months = self.hr_employee.company_id.duration_after_recruitment

            upcoming_appraisal_date = date.today() + relativedelta(months=months)

            self.assertEqual(self.hr_employee.next_appraisal_date, upcoming_appraisal_date, 'next_appraisal_date is not set properly')

        with freeze_time(self.hr_employee.next_appraisal_date):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertTrue(appraisals, "Appraisal not created by appraisal plan at next_appraisal_date")

    def test_08_check_new_employee_no_appraisal(self):
        """
            Employee has started working recenlty
            less than duration_after_recruitment ago,
            check that appraisal is not set
        """
        with freeze_time(date.today() - relativedelta(months=3)):
            self.hr_employee.last_ongoing_appraisal_date = date.today()

            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertFalse(appraisals, "Appraisal created")

    def test_09_check_appraisal_after_recruitment(self):
        """
            Employee has started working recently
            Time for a first appraisal after
            some time (duration_after_recruitment) has evolved
            since recruitment
        """
        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertTrue(appraisals, "Appraisal not created")

    def test_10_check_no_appraisal_since_recruitment_appraisal(self):
        """
            After employees first recruitment appraisal some time has evolved,
            but not enough for the first real appraisal.
            Check that appraisal is not created
        """
        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment)):
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today(),
                'state': '3_done',
            })
            self.hr_employee.last_ongoing_appraisal_date = date.today()
        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment + self.duration_first_appraisal - 2)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id), ('state', '=', '1_new')])
            self.assertFalse(appraisals, "Appraisal created")

    def test_11_check_first_appraisal_since_recruitment_appraisal(self):
        """
            Employee started while ago, has already had
            first recruitment appraisal and now it is
            time for a first real appraisal
        """
        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment)):
            # In order to make the second appraisal, cron checks that
            # there is alraedy one done appraisal for the employee
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today(),
                'state': '3_done',
            })
            self.hr_employee.last_ongoing_appraisal_date = date.today()

        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment + self.duration_first_appraisal)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertTrue(appraisals, "Appraisal not created")

    def test_12_check_no_appraisal_after_first_appraisal(self):
        """
            Employee has already had first recruitment appraisal
            and first real appraisal, but its not time yet
            for recurring appraisal. Check that
            appraisal is not set
        """
        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment + self.duration_first_appraisal)):
            # In order to make recurring appraisal, cron checks that
            # there are alraedy two done appraisals for the employee
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today() - relativedelta(months=self.duration_first_appraisal),
                'state': '3_done',
            })
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today(),
                'state': '3_done',
            })
            self.hr_employee.last_ongoing_appraisal_date = date.today()

        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment + self.duration_first_appraisal + self.duration_next_appraisal - 2)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id), ('state', '=', '1_new')])
            self.assertFalse(appraisals, "Appraisal created")

    def test_12_check_recurring_appraisal(self):
        """
            check that recurring appraisal is created
        """
        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment + self.duration_first_appraisal)):
            # In order to make recurring appraisal, cron checks that
            # there are alraedy two done appraisals for the employee
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today() - relativedelta(months=self.duration_first_appraisal),
                'state': '3_done',
            })
            self.HrAppraisal.create({
                'employee_id': self.hr_employee.id,
                'date_close': date.today(),
                'state': '3_done',
            })
            self.hr_employee.last_ongoing_appraisal_date = date.today()

        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment + self.duration_first_appraisal + self.duration_next_appraisal)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertTrue(appraisals, "Appraisal not created")

    def test_load_scenario(self):
        self.env['hr.appraisal']._load_demo_data()

    def test_create_appraisal_without_hr_right(self):
        user_without_hr_right = self.env['res.users'].create({
            'name': 'Test without hr right',
            'login': 'test_without_hr_right',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            'notification_type': 'email',
        })
        user_without_hr_right.action_create_employee()
        appraisal_form = Form(self.env['hr.appraisal'].with_user(user_without_hr_right).with_context({'uid': user_without_hr_right.id}))
        appraisal_form.save()

    def test_create_appraisal_campaign_without_hr_right(self):
        user_without_hr_right = self.env['res.users'].create({
            'name': 'Test without hr right',
            'login': 'test_without_hr_right',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            'notification_type': 'email',
        })
        user_without_hr_right.action_create_employee()
        employees = self.env['hr.employee'].create([
            {
                'name': 'Emp1',
                'parent_id': user_without_hr_right.employee_ids[0].id,
            }, {
                'name': 'Emp2',
                'parent_id': user_without_hr_right.employee_ids[0].id,
            }
        ])
        appraisal_template = self.env['hr.appraisal.template'].create({'description': 'Test appraisal template'})
        appraisal_campaign_form = Form(self.env['hr.appraisal.campaign.wizard'].with_user(user_without_hr_right).with_context(
            {'uid': user_without_hr_right.id}
        ))
        appraisal_campaign_form.employee_ids = employees
        appraisal_campaign_form.appraisal_template_id = appraisal_template
        appraisal_campaign = appraisal_campaign_form.save()
        appraisal_campaign.action_generate_appraisals()

    def _set_appraisal_data(self, appraisal):
        appraisal.employee_feedback = self.employee_feedback
        appraisal.manager_feedback = self.manager_feedback
        appraisal.assessment_note = self.appraisal_rating

    def test_reopen_appraisal(self):
        appraisal = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() + relativedelta(months=1),
            'state': '2_pending',
        })
        self._set_appraisal_data(appraisal)
        appraisal.action_done()
        appraisal.action_reopen()
        self.assertEqual(appraisal.state, '2_pending', "A reopened appraisal should be in the pending state")
        self.assertEqual(appraisal.employee_feedback, self.employee_feedback, "Employee feedback should stay the same after the appraisal is reopened")
        self.assertEqual(appraisal.manager_feedback, self.manager_feedback, "Manager feedback should stay the same after the appraisal is reopened")
        self.assertEqual(appraisal.assessment_note, self.appraisal_rating, "Appraisal rating shouldn't change when an appraisal is reopened")

    def _get_appraisal_count(self, user):
        return self.env['hr.appraisal'].with_user(user).search_count([
            ('employee_id', '=', self.hr_employee.id),
        ])

    def test_appraisal_with_employee_officer(self):
        """
        This test checks that an admin can see appraisals of all employees,
        while an employee officer can only see appraisals where they are
        the appraiser.
        """
        admin_user = self.env.ref('base.user_admin')
        if not admin_user.employee_id:
            admin_user.action_create_employee()

        officer_group = self.env.ref('hr.group_hr_manager')
        officer_user = self.env['res.users'].create({
            'name': 'Employee Officer',
            'login': 'employee_officer',
            'group_ids': [(6, 0, [officer_group.id])],
            'notification_type': 'email',
        })
        officer_user.action_create_employee()

        # Create appraisal A with admin as appraiser
        appraisal_a = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'manager_ids': [(6, 0, [admin_user.employee_id.id])],
            'date_close': date.today() + relativedelta(months=1),
            'state': '1_new',
        })

        self.assertEqual(self._get_appraisal_count(admin_user), 1)
        self.assertEqual(self._get_appraisal_count(officer_user), 0)

        # opening employee appraisals should not fail
        self.hr_employee.with_user(officer_user).action_open_employee_appraisals()

        # Create appraisal B with officer as appraiser
        self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'manager_ids': [(6, 0, [officer_user.employee_id.id])],
            'date_close': date.today() + relativedelta(months=1),
            'state': '1_new',
        })

        self.assertEqual(self._get_appraisal_count(admin_user), 2)
        self.assertEqual(self._get_appraisal_count(officer_user), 1)

        # Delete appraisal A
        appraisal_a.sudo().unlink()

        self.assertEqual(self._get_appraisal_count(admin_user), 1)
        self.assertEqual(self._get_appraisal_count(officer_user), 1)

    def test_appraisal_departement_from_employee(self):
        self.assertEqual(self.hr_employee.department_id, self.dep_rd)

        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertEqual(appraisals.department_id, self.dep_rd)

    def test_appraisal_template_computation(self):
        # Delete all templates to prevent them from interacting with the test
        for template in self.env['hr.appraisal.template'].search([]):
            template.unlink()

        test_template = self.env['hr.appraisal.template'].create({'description': 'Test appraisal template'})
        test_template.company_id = self.env.company
        self.hr_employee.department_id = False

        with freeze_time(self.hr_employee.date_version + relativedelta(months=self.duration_after_recruitment)):
            self.env['res.company']._run_employee_appraisal_plans()
            appraisals = self.HrAppraisal.search([('employee_id', '=', self.hr_employee.id)])
            self.assertEqual(appraisals.appraisal_template_id, test_template)

    def test_appraisal_template_keeps_generic_choice_on_state_change(self):
        self.env['hr.appraisal.template'].search([]).unlink()
        Template = self.env['hr.appraisal.template']
        Template.create({'description': 'First Generic Template'})
        selected_template = Template.create({'description': 'Selected Generic Template'})

        appraisal = self.HrAppraisal.create({'employee_id': self.colleague.id})
        appraisal.appraisal_template_id = selected_template

        appraisal.action_confirm()
        self.assertEqual(appraisal.appraisal_template_id, selected_template)

        appraisal.action_back()
        self.assertEqual(appraisal.appraisal_template_id, selected_template)

    def test_check_next_appraisal_date_is_unset_for_archived_employee(self):
        """
            Check that when an employee is archived,
            its next_appraisal_date is unset.
        """
        self.hr_employee.next_appraisal_date = date.today() + relativedelta(months=6)
        self.hr_employee.action_archive()
        self.assertFalse(self.hr_employee.next_appraisal_date, 'next_appraisal_date should be empty for archived employee')

    def test_check_appraisals_and_goals_after_employees_departure(self):
        """
        In case of end of collaboration with an employee:
        - all their future appraisals should be removed
        - the employee should be removed from manager_ids in appraisals
        - all their personal goals should be archived
        """
        future_appraisal_new = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() + relativedelta(months=2),
            'manager_ids': [(6, 0, [self.manager.id])],
            'state': '1_new'
        })
        future_appraisal_pending = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() + relativedelta(months=1),
            'manager_ids': [(6, 0, [self.manager.id])],
            'state': '2_pending'
        })
        completed_appraisal = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
            'date_close': date.today() + relativedelta(months=-1),
            'manager_ids': [(6, 0, [self.manager.id])],
            'state': '3_done'
        })
        goal_test = self.env['hr.appraisal.goal'].create({
            'name': 'Goal Test',
            'employee_ids': [(6, 0, [self.hr_employee.id])],
            'manager_ids': [(6, 0, [self.manager.id])],
        })
        self.assertTrue(future_appraisal_new, "Appraisal in state 'new' has not been created")
        self.assertTrue(future_appraisal_pending, "Appraisal in state 'pending' has not been created")
        self.assertTrue(completed_appraisal, "Appraisal in state 'done' has not been created")
        self.assertTrue(goal_test, "Goal has not been created")

        # appraiser leaves the company
        self.manager.date_version = date.today() + relativedelta(years=-1)
        self.env['hr.employee.departure'].create({
            'employee_id': self.manager.id,
            'dismissal_date': date.today() + relativedelta(days=-1),
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
        }).action_register()

        self.assertFalse(future_appraisal_new.manager_ids, "Manager wasn't removed from appraisal after departure")
        self.assertFalse(future_appraisal_pending.manager_ids, "Manager wasn't removed from appraisal after departure")

        # employee leaves the company
        self.env['hr.employee.departure'].create({
            'employee_id': self.hr_employee.id,
            'dismissal_date': date.today() + relativedelta(days=-1),
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
        }).action_register()

        self.assertFalse(future_appraisal_new.exists(), "Appraisal in state 'new' was not removed after employee's departure")
        self.assertFalse(future_appraisal_pending.exists(), "Appraisal in state 'pending' was not removed after employee's departure")
        self.assertTrue(completed_appraisal.exists(), "Appraisal in state 'done' was removed")
        self.assertFalse(goal_test.active, "Personal goal was not archived after employee's departure")

    def test_default_appraisal_template(self):
        """ Choose first template_id which matches either of the condition:
            1. The template's department matches the employee's department.
            2. The template has no department assigned.
        """
        # archive all templates to prevent them from interacting with this test
        self.env['hr.appraisal.template'].search([]).unlink()

        _, rd_dep_template, default_template = self.env['hr.appraisal.template'].create([
            {
                'description': 'appraisal template(Sales)',
                'department_ids': [Command.create({'name': 'sales Test'})],
                'sequence': 1,
            }, {
                'description': 'appraisal template(RD Department)',
                'department_ids': [Command.link(self.dep_rd.id)],
                'sequence': 2,
            }, {
                'description': 'default template',
                'sequence': 3,
            },
        ])

        employee_appraisal1 = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
        })
        self.assertEqual(employee_appraisal1.appraisal_template_id, rd_dep_template, 'employee belong to dep_rd department')

        # updating the priority of templates.
        default_template.sequence = 2
        rd_dep_template.sequence = 3

        employee_appraisal2 = self.HrAppraisal.create({
            'employee_id': self.hr_employee.id,
        })
        self.assertEqual(employee_appraisal2.appraisal_template_id, default_template, 'first template without and dep gets priority')

    def test_request_late_appraisal(self):
        """Tests that requesting an appraisal after next_appraisal_date properly creates the appraisal"""
        old_appraisal_date = self.hr_employee.next_appraisal_date
        with freeze_time(self.hr_employee.next_appraisal_date + relativedelta(days=7)):
            with Form.from_action(self.env, self.hr_employee.with_context({"uid": self.manager_user.id}).action_send_appraisal_request()) as form:
                form.employee_id = self.hr_employee
                appraisal = form.save()
            self.assertTrue(appraisal.exists())
            self.assertEqual(self.hr_employee.next_appraisal_date, date.today())

        with freeze_time(old_appraisal_date - relativedelta(days=7)):
            self.hr_employee.next_appraisal_date = old_appraisal_date
        with freeze_time(self.hr_employee.next_appraisal_date + relativedelta(days=7)):
            with Form.from_action(self.env, self.manager.with_context({"uid": self.manager_user.id}).action_send_appraisal_request()) as form:
                form.employee_id = self.manager
                appraisal = form.save()
            self.assertTrue(appraisal.exists())
            with Form(appraisal) as form:
                form.employee_id = self.hr_employee
            self.assertEqual(self.hr_employee.next_appraisal_date, date.today())
