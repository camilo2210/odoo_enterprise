from odoo.addons.planning_field_service.controllers.portal import PlanningFieldServiceCustomerPortal


class CustomerFsmPortal(PlanningFieldServiceCustomerPortal):

    def _get_additional_intervention_data(self, intervention_sudo):
        intervention_data = super()._get_additional_intervention_data(intervention_sudo)
        intervention_data['show_portal_worksheet'] = (
            intervention_sudo.worksheet_template_id
            and any(intervention_sudo.worksheet_properties.values()) or intervention_sudo.has_studio_worksheet_fields
        )
        # ensure photos are accessible with access token inside template
        intervention_sudo.photo_ids.generate_access_token()
        return intervention_data
