from odoo.tests import HttpCase, tagged
import json
import re


@tagged('post_install', '-at_install')
class TestApplicantQualificationStageChange(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        Employees = cls.env['hr.employee']

        # Recruitment user groups
        group_recruitment_interviewer = cls.env.ref('hr_recruitment.group_hr_recruitment_interviewer')
        group_recruitment_user = cls.env.ref('hr_recruitment.group_hr_recruitment_user')

        cls.user_recruitment_officer = Users.create({
            'name': 'bedo',
            'login': 'bedo',
            'email': 'bedo@example.com',
            'group_ids': [(6, 0, [group_recruitment_user.id])]
        })

        cls.employee_recruitment_officer = Employees.create({
            'name': 'Bedo Employee',
            'user_id': cls.user_recruitment_officer.id,
        })

        cls.user_recruitment_interviewer = Users.create({
            'name': 'interviewer',
            'login': 'interviewer',
            'password': 'interviewer',
            'email': 'interviewer@example.com',
            'group_ids': [(6, 0, [group_recruitment_interviewer.id])]
        })

        # Department + Job
        dep_rd = cls.env['hr.department'].create({'name': 'Research & Development'})
        job = cls.env['hr.job'].create({
            'name': 'Test Job',
            'department_id': dep_rd.id,
            'no_of_recruitment': 5,
            'interviewer_ids': [(4, cls.user_recruitment_interviewer.id)]
        })

        # Applicant
        cls.applicant = cls.env['hr.applicant'].sudo().create({
            'partner_name': 'Test Applicant',
            'job_id': job.id,
            'recruiter_id': cls.employee_recruitment_officer.id,
        })

        # Stage + template
        schedule_tmpl = cls.env.ref(
            'appointment_hr_recruitment.email_template_data_applicant_schedule_interview'
        )
        cls.q_stage = cls.env['hr.recruitment.stage'].search([('name', '=', 'Qualification')])
        cls.q_stage.write({'template_id': schedule_tmpl.id})

    def test_stage_change_via_write_rpc(self):
        # Login as interviewer
        self.authenticate('interviewer', 'interviewer')

        ctx = {
            "lang": "en_US",
            "tz": "Europe/Brussels",
            "uid": self.user_recruitment_interviewer.id,
            "allowed_company_ids": [self.env.company.id],
        }

        # ----------------------------------------------------------
        # STEP 1 — Perform a "write" on hr.applicant
        # ----------------------------------------------------------
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "hr.applicant",
                "method": "write",
                "args": [
                    [self.applicant.id],
                    {"stage_id": self.q_stage.id},
                ],
                "kwargs": {
                    "context": ctx,
                }
            },
            "id": 1,
        }

        resp = self.url_open(
            "/web/dataset/call_kw",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        ).json()

        # write() returns True/False
        self.assertIn("result", resp)
        self.assertTrue(resp["result"], "Write RPC failed")

        # ----------------------------------------------------------
        # STEP 2 — Verify that the interview invitation email was sent
        # ----------------------------------------------------------
        applicant = self.env['hr.applicant'].browse(self.applicant.id)

        messages = [m for m in applicant.message_ids if m.body]
        self.assertTrue(messages, "No messages found for applicant")

        msg = sorted(messages, key=lambda m: m.id)[-1]
        body = msg.body

        self.assertIn("Thanks for your application", body)
        self.assertIn("Schedule my interview", body)

        # ----------------------------------------------------------
        # STEP 3 — Extract and validate the booking URL
        # ----------------------------------------------------------
        match = re.search(r'href="([^"]+)"', body)
        self.assertIsNotNone(match, "No URL found in message body")

        url = match.group(1)

        # Must contain /book/<token>?applicant_code=<code>
        pattern = r'/book/[^?]+\?applicant_code=[^&]+'
        self.assertRegex(url, pattern, f"URL missing expected format: {url}")

        # Open the booking page to ensure it's valid
        page = self.url_open(url)
        self.assertEqual(page.status_code, 200, "Booking page did not open successfully")
