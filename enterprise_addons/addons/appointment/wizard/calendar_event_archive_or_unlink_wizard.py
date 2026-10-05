from odoo import api, models


class CalendarEventArchiveOrUnlinkWizard(models.TransientModel):
    _name = 'calendar.event.archive.or.unlink.wizard'
    _inherit = ['calendar.event.archive.or.unlink.wizard']

    @api.depends('calendar_event_id')
    def _compute_template_id(self):
        """To notify as many attendees as possible, the default cancellation template from calendar is used if the default
        templates of the appointment type and the appointment app are not found."""
        appointment_wizards_no_template = self.env['calendar.event.archive.or.unlink.wizard']
        appointment_wizards_to_notify = self.filtered(lambda wizard: wizard.calendar_event_id.appointment_type_id)
        appointment_wizards_per_template = appointment_wizards_to_notify.grouped(
            lambda wizard: wizard.calendar_event_id.appointment_type_id.canceled_mail_template_id
        )
        for template, appointment_wizards in appointment_wizards_per_template.items():
            if template:
                appointment_wizards.template_id = template
            # As there is only one group without template, the sending from the default mail template can be done in the loop.
            elif default_template := self.env.ref('appointment.appointment_canceled_mail_template', raise_if_not_found=False):
                appointment_wizards.template_id = default_template
            else:
                appointment_wizards_no_template = appointment_wizards
        super(CalendarEventArchiveOrUnlinkWizard, self - appointment_wizards_to_notify + appointment_wizards_no_template)._compute_template_id()
