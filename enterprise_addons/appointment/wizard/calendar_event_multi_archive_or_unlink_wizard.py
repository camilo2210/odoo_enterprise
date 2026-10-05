from odoo import api, models


class CalendarEventMultiArchiveOrUnlinkWizard(models.TransientModel):
    _name = 'calendar.event.multi.archive.or.unlink.wizard'
    _inherit = ['calendar.event.multi.archive.or.unlink.wizard']

    @api.model
    def _send_mails_from_template(self, events_to_notify):
        """To notify as many attendees as possible, the default cancellation template from calendar is used if the default
        templates of the appointment type and the appointment app are not found."""
        bookings_no_template = self.env['calendar.event']
        bookings_to_notify = events_to_notify.filtered('appointment_type_id')
        bookings_per_template = bookings_to_notify.grouped(lambda e: e.appointment_type_id.canceled_mail_template_id)
        for template, bookings in bookings_per_template.items():
            if template:
                template.send_mail_batch(bookings.ids)
            # As there is only one group without template, the sending from the default mail template can be done in the loop.
            elif default_template := self.env.ref('appointment.appointment_canceled_mail_template', raise_if_not_found=False):
                default_template.send_mail_batch(bookings.ids, email_values={'res_id': False})
            else:
                bookings_no_template = bookings
        super()._send_mails_from_template(events_to_notify - bookings_to_notify + bookings_no_template)
