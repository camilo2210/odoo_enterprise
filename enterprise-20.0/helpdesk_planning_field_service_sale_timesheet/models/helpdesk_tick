from odoo import models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _get_intervention_action(self):
        action = super()._get_intervention_action()
        action['context'].update(
            default_sale_line_id=self.sale_line_id.id,
            default_project_id=self.project_id.id,
        )
        return action
