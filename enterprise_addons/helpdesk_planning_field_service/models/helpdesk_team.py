# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _mail_get_message_subtypes(self):
        res = super()._mail_get_message_subtypes()
        if len(self) == 1:
            intervention_completed_subtype = self.env.ref('helpdesk_planning_field_service.mt_ticket_intervention_completed')
            if not self.use_fsm and intervention_completed_subtype in res:
                res -= intervention_completed_subtype
        return res
