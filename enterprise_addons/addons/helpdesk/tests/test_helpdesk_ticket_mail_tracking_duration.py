from datetime import datetime

from odoo.tests import tagged

from odoo.addons.mail.tests.common_tracking import MailTrackingDurationMixinCase


@tagged('mail_track', 'mail_duration_mixin')
class TestHelpdeskTicketMailTrackingDuration(MailTrackingDurationMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass('helpdesk.ticket')

    def test_helpdesk_ticket_mail_tracking_duration(self):

        stage_1, stage_2, stage_3, stage_4 = self.env["helpdesk.stage"].create([
            {"name": "New"},
            {"name": "In Progress"},
            {"name": "On Hold"},
            {"name": "Solved"},
        ])

        calendar = self.env['resource.calendar'].create({
            'name': 'Standard 40h/week',
            'attendance_ids': [
                (0, 0, {
                    'dayofweek': weekday,
                    'hour_from': hour,
                    'hour_to': hour + 4,
                })
                for weekday in ['0', '1', '2', '3', '4']
                for hour in (8, 13)
            ],
        })

        team_1, team_2 = self.env["helpdesk.team"].create([
            {"name": "Helpdesk Team 1", "resource_calendar_id": calendar.id},
            {"name": "Helpdesk Team 2", "resource_calendar_id": False},
        ])

        mocked_time = datetime.strptime('2026-02-02 08:00:00', "%Y-%m-%d %H:%M:%S")
        with self.mock_datetime_and_now(mocked_time):
            tickets = self.env["helpdesk.ticket"].create([
                {"name": "Ticket 1", "stage_id": stage_1.id, "team_id": team_1.id},
                {"name": "Ticket 2", "stage_id": stage_1.id, "team_id": team_2.id},
            ])
            self.env.flush_all()

        transitions = [
            ("2026-02-02 09:00:00", stage_2),
            ("2026-02-02 10:00:00", stage_3),
            ("2026-02-02 14:00:00", stage_4),
        ]

        for time_str, stage in transitions:
            mocked_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            with self.mock_datetime_and_now(mocked_time):
                if stage:
                    tickets.stage_id = stage
                    tickets[0]._compute_duration_stage_tracking()
                    tickets[1]._compute_duration_tracking()
                self.env.flush_all()

        final_time = datetime(2026, 2, 2, 16, 0, 0)
        with self.mock_datetime_and_now(final_time):
            # Ticket with working calendar
            self.assertDictEqual(tickets[0].duration_stage_tracking, {
                str(stage_1.id): 60.0,
                str(stage_2.id): 60.0,
                str(stage_3.id): 180.0,  # 10:00 -> 14:00 (3 working hours)
                's': stage_4.id,
                'd': "2026-02-02 14:00:00",
            })

            # Ticket without calendar
            self.assertDictEqual(tickets[1].duration_tracking, {
                str(stage_1.id): 60.0,
                str(stage_2.id): 60.0,
                str(stage_3.id): 240.0,  # 10:00 -> 14:00 (4 hours)
                str(stage_4.id): 0,
                's': stage_4.id,
                'd': "2026-02-02 14:00:00",
            })
