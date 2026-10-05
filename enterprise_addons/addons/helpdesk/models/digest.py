# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class DigestDigest(models.Model):
    _inherit = 'digest.digest'

    kpi_helpdesk_tickets_closed = fields.Boolean('Tickets Closed')
    kpi_helpdesk_tickets_closed_value = fields.Integer(compute='_compute_kpi_helpdesk_tickets_closed_value', export_string_translation=False)

    def _compute_kpi_helpdesk_tickets_closed_value(self):
        self._raise_if_not_member_of('helpdesk.group_helpdesk_user')
        self._calculate_kpi(
            'helpdesk.ticket',
            'kpi_helpdesk_tickets_closed_value',
            date_field='close_date',
        )

    def _get_kpi_custom_settings(self, company, user):
        res = super()._get_kpi_custom_settings(company, user)
        menu_id = self.env.ref('helpdesk.menu_helpdesk_root').id
        res['kpi_action']['kpi_helpdesk_tickets_closed'] = (
            f'helpdesk.helpdesk_team_dashboard_action_main?menu_id={menu_id}')
        res['kpi_sequence']['kpi_helpdesk_tickets_closed'] = 8500
        return res
