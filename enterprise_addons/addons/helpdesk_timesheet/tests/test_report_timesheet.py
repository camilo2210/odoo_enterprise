from odoo.tests import tagged

from odoo.addons.helpdesk_timesheet.tests.common import TestHelpdeskTimesheetCommon


@tagged('post_install', '-at_install')
class TestReportTimesheetTicket(TestHelpdeskTimesheetCommon):
    """ Check the 'Timesheets' printable report is generated with the right entries when
        printed from a helpdesk ticket.
    """

    def _render_report(self, report_xml_id, records):
        return self.env['ir.actions.report']._render_qweb_html(report_xml_id, records.ids)[0].decode()

    def test_report_from_ticket(self):
        timesheet = self.env['account.analytic.line'].create({
            'name': 'Timesheet on the ticket',
            'helpdesk_ticket_id': self.helpdesk_ticket.id,
            'unit_amount': 3.0,
            'employee_id': self.empl_employee.id,
        })
        self.assertEqual(self.helpdesk_ticket.timesheet_ids, timesheet)

        report = self._render_report('helpdesk_timesheet.timesheet_report_ticket', self.helpdesk_ticket)
        self.assertIn(self.helpdesk_ticket.name, report)
        self.assertIn('Timesheet on the ticket', report)
        self.assertIn(self.user_employee.partner_id.name, report)

    def test_report_from_ticket_without_timesheet(self):
        report = self._render_report('helpdesk_timesheet.timesheet_report_ticket', self.helpdesk_ticket)
        self.assertNotIn('Timesheet on the ticket', report)
