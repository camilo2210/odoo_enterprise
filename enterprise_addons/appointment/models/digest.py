# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Digest(models.Model):
    _inherit = 'digest.digest'

    kpi_nbr_of_online_appointment = fields.Boolean('Booked Appointments')
    kpi_nbr_of_online_appointment_value = fields.Integer(
        compute='_compute_kpi_nbr_of_online_appointment_value')

    def _compute_kpi_nbr_of_online_appointment_value(self):
        self._raise_if_not_member_of('appointment.group_appointment_manager')
        self._calculate_kpi(
            'calendar.event',
            digest_kpi_field='kpi_nbr_of_online_appointment_value',
            additional_domain=[('appointment_type_id', '!=', False)],
            is_cross_company=True)

    def _get_kpi_custom_settings(self, company, user):
        res = super()._get_kpi_custom_settings(company, user)
        menu_id = self.env.ref('appointment.main_menu_appointments').id
        res['kpi_action']['kpi_nbr_of_online_appointment'] = (
            f'appointment.calendar_event_action_appointment_reporting?menu_id={menu_id}')
        res['kpi_sequence']['kpi_nbr_of_online_appointment'] = 4500
        return res
