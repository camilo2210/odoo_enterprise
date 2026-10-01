# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.appointment.controllers.appointment import AppointmentController


class WebsiteAppointment(AppointmentController):

    # ------------------------------------------------------------
    # APPOINTMENT INDEX PAGE
    # ------------------------------------------------------------

    def appointment_type_index_sitemap(env, rule, qs):
        Appointment = env['appointment.type']
        domain = [('is_published', '=', True)]
        appointments = Appointment.search(domain, limit=2)

        if len(appointments) == 1:
            loc = f'/appointment/{appointments[0].id}'
        else:
            loc = '/appointment'

        if not qs or qs.lower() in loc.lower():
            yield {'loc': loc}

    @http.route(sitemap=appointment_type_index_sitemap)
    def appointment_type_index(self, page=1, **kwargs):
        """
        Display the appointments to choose (the display depends of a custom option called 'Card Design')

        :param page: the page number displayed when the appointments are organized by cards

        A param filter_appointment_type_ids can be passed to display a define selection of appointments types.
        This param is propagated through templates to allow people to go back with the initial appointment
        types filter selection
        """
        kwargs['domain'] = self._appointments_base_domain(
            filter_appointment_type_ids=kwargs.get('filter_appointment_type_ids'),
            search=kwargs.get('search'),
            invite_token=kwargs.get('invite_token'),
            additional_domain=self._appointment_website_domain(),
            filter_countries=True,
        )
        available_appointment_types = self._fetch_and_check_private_appointment_types(
            kwargs.get('filter_appointment_type_ids'),
            kwargs.get('filter_staff_user_ids'),
            kwargs.get('filter_resource_ids'),
            kwargs.get('invite_token'),
            domain=kwargs['domain'],
        )
        if len(available_appointment_types) == 1 and not kwargs.get('search'):
            # If there is only one appointment type available in the selection, skip the appointment type selection view
            return request.redirect('%s?%s' % (available_appointment_types.website_url, keep_query('*')))

        return request.render(
            'website_appointment.appointments_selection_layout',
            self._prepare_appointments_data(
                page, available_appointment_types,
                **kwargs
            )
        )

    # ----------------------------------------------------------------
    # APPOINTMENT SUBMISSION : RECAPTCHA CHECK
    # ---------------------------------------------------------------- 
    @http.route()
    def appointment_form_submit(self, *args, **kwargs):
        request.env['ir.http']._verify_request_recaptcha_token('appointment_form_submission')
        # Ensure the visitor is recorded for the test_appointment_forced_staff_user_tour
        request.env['ir.http']._get_visitor_from_request(force_create=True)
        return super().appointment_form_submit(*args, **kwargs)

    # Tools / Data preparation
    # ------------------------------------------------------------

    def _prepare_appointments_data(self, page, appointment_types, **kwargs):
        """
            Compute specific data for the appointment selection layout like the search bar and the pager.
        """
        APPOINTMENTS_PER_PAGE = 12
        appointment_count = len(appointment_types)

        pager = self.env.website.pager(
            url='/appointment',
            url_args=kwargs,
            total=appointment_count,
            page=page,
            step=APPOINTMENTS_PER_PAGE,
            scope=5,
        )
        appointment_types = appointment_types.sorted('is_published', reverse=True)[pager['offset']:pager['offset'] + APPOINTMENTS_PER_PAGE]

        return {
            'appointment_types': appointment_types,
            'current_search': kwargs.get('search'),
            'pager': pager,
            'filter_appointment_type_ids': kwargs.get('filter_appointment_type_ids'),
            'filter_staff_user_ids': kwargs.get('filter_staff_user_ids'),
            'invite_token': kwargs.get('invite_token'),
            'search_count': appointment_count,
            'structured_data': appointment_types._render_jsonld(),
        }

    def _prepare_appointment_type_page_values(self, appointment_type, staff_user_id=False, resource_selected_id=False, **kwargs):
        values = super()._prepare_appointment_type_page_values(appointment_type, staff_user_id, resource_selected_id, **kwargs)
        values['structured_data'] = appointment_type._render_jsonld(is_detail_page=True)
        return values

    def _get_allowed_companies(self, organizer):
        """ Check if the current website can be used to determine the company
        and fallback on the companies of the organizer if not """
        companies = super()._get_allowed_companies(organizer)
        website_company = self.env.website.company_id
        return website_company if website_company in companies else companies

    def _get_customer_partner(self):
        """ Get the partner of the last calendar event of the public user's
        visitor if no partner has been found from the user or visitor, to
        avoid partner duplication if the user is not logged. """
        partner = super()._get_customer_partner()
        if not partner:
            visitor = request.env['ir.http']._get_visitor_from_request()
            if visitor.partner_id:
                partner = visitor.partner_id
            elif visitor and request.env.user._is_public():
                partner = self.env['calendar.event'].sudo().search(
                    [('visitor_id', '=', visitor.id), ('appointment_booker_id', '!=', False)],
                    order='id desc',
                    limit=1
                ).appointment_booker_id
        return partner

    @staticmethod
    def _get_customer_country():
        """
            Find the country from the geoip lib or fallback on the user or the visitor
        """
        country = AppointmentController._get_customer_country()
        if not country:
            visitor = request.env['ir.http']._get_visitor_from_request()
            country = visitor.country_id
        return country

    @classmethod
    def _appointments_base_domain(cls, filter_appointment_type_ids, search=False, invite_token=False, additional_domain=None, filter_countries=False):
        domain = super()._appointments_base_domain(filter_appointment_type_ids, search, invite_token, additional_domain, filter_countries)
        domain &= request.env.website.website_domain()
        return domain
