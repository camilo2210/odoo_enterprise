from odoo import fields, models


class CalendarAlarm(models.Model):
    _inherit = 'calendar.alarm'

    appointment_type_ids = fields.Many2many('appointment.type', string="Appointments")
