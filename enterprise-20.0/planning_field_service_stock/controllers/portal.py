from odoo.addons.planning_field_service.controllers.portal import PlanningFieldServiceCustomerPortal
from odoo.http import request


class CustomerPortal(PlanningFieldServiceCustomerPortal):

    def _get_additional_intervention_data(self, intervention_sudo):
        intervention_data = super()._get_additional_intervention_data(intervention_sudo)
        intervention_data['show_portal_equipment'] = request.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_equipment')
        return intervention_data
