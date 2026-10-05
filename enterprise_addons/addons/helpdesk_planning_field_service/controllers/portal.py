# Part of Odoo. See LICENSE file for full copyright and licensing details.
from werkzeug.exceptions import NotFound

from odoo.http import request, route
from odoo.exceptions import AccessError, MissingError
from odoo.tools import format_datetime, get_lang

from odoo.addons.helpdesk.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.planning_field_service.controllers.portal import PlanningFieldServiceCustomerPortal


class HelpdeskPlanningFieldServiceCustomerPortal(PlanningFieldServiceCustomerPortal, CustomerPortal):

    def _get_additional_intervention_data(self, intervention_sudo):
        intervention_data = super()._get_additional_intervention_data(intervention_sudo)
        try:
            if intervention_sudo.helpdesk_ticket_id and self._document_check_access('helpdesk.ticket', intervention_sudo.helpdesk_ticket_id.id):
                intervention_data['intervention_link_section'].append({
                    'access_url': intervention_sudo.helpdesk_ticket_id.get_portal_url(),
                    'title': request.env._('Ticket'),
                })
        except (AccessError, MissingError):
            pass

        return intervention_data

    def _ticket_get_page_view_values(self, ticket, access_token, **kwargs):
        values = super()._ticket_get_page_view_values(ticket, access_token, **kwargs)
        if request.env['planning.slot']._show_portal_field_service() and ticket.sudo().planning_slot_count:
            domain = self.env['planning.slot']._get_intervention_reports_domain([('helpdesk_ticket_id', 'in', ticket.ids)])
            interventions = request.env['planning.slot'].sudo().search(domain)
            if interventions:
                title = request.env._('Field Service')
                if len(interventions) == 1:
                    ticket_intervention_url = f'/my/field-service/{interventions.id}?access_token={interventions.access_token}'
                else:
                    ticket_intervention_url = f'/my/tickets/{ticket.id}/interventions'
                values['ticket_link_section'].append({
                    'access_url': ticket_intervention_url,
                    'title': title,
                    'sequence': 3,
                })
        return values

    @route([
        '/my/tickets/<ticket_id>/interventions',
        '/my/tickets/<ticket_id>/interventions/page/<int:page>'
    ], type='http', auth="user", website=True)
    def portal_my_tickets_field_service_interventions(self, ticket_id=None, page=1):
        ticket = request.env['helpdesk.ticket'].search([('id', '=', ticket_id)])
        if not (ticket.exists() and request.env['planning.slot']._show_portal_field_service()):
            return NotFound()
        PlanningSlot = request.env['planning.slot']
        domain = PlanningSlot._get_intervention_reports_domain([('helpdesk_ticket_id', 'in', ticket.ids)])
        values = self._prepare_portal_layout_values()
        path = 'field-service'
        url = f'/my/{path}'
        pager = portal_pager(url, PlanningSlot.sudo().search_count(domain), page=page, step=self._items_per_page)
        values.update(
            default_url=url,
            interventions=PlanningSlot.sudo().search(domain, limit=self._items_per_page, offset=pager['offset']),
            pager=pager,
            format_datetime=lambda dt, dt_format: format_datetime(request.env, dt, dt_format=dt_format, tz=request.env.tz or 'UTC', lang_code=get_lang(request.env).code),
        )
        request.session['my_field_service_history'] = values['interventions'].ids[:100]
        return request.render('planning_field_service.portal_my_field_service_report_list', values)
