import binascii

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import format_datetime, get_lang

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class PlanningFieldServiceCustomerPortal(CustomerPortal):

    def _prepare_portal_counter_values(self, counter):
        if counter == 'field_service_count':
            model_name = 'planning.slot'
            domain = request.env[model_name]._get_intervention_reports_domain()
            return model_name, domain, 'sudo'
        return super()._prepare_portal_counter_values(counter)

    @http.route(['/my/field-service', '/my/field-service/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_field_service_interventions_list(self, page=1, filterby='all'):
        PlanningSlot = request.env['planning.slot']
        searchbar_filters = {
            'all': {'label': request.env._('All'), 'domain': Domain.TRUE},
            'to_review': {'label': request.env._('To Review'), 'domain': Domain('worksheet_signature', '=', False)},
            'signed': {'label': request.env._('Signed'), 'domain': Domain('worksheet_signature', '!=', False)},
        }
        if filterby not in searchbar_filters:
            filterby = 'all'
        domain = PlanningSlot._get_intervention_reports_domain(searchbar_filters[filterby]['domain'])
        values = self._prepare_portal_layout_values()
        path = 'field-service'
        url = f'/my/{path}'
        pager = portal_pager(url, PlanningSlot.sudo().search_count(domain), page=page, step=self._items_per_page)
        values.update(
            default_url=url,
            interventions=PlanningSlot.sudo().search(domain, limit=self._items_per_page, offset=pager['offset']),
            pager=pager,
            searchbar_filters=searchbar_filters,
            filterby=filterby,
            page_name='field_service',
            format_datetime=lambda dt, dt_format: format_datetime(request.env, dt, dt_format=dt_format, tz=request.env.tz or 'UTC', lang_code=get_lang(request.env).code),
        )
        request.session['my_field_service_history'] = values['interventions'].ids[:100]
        return request.render('planning_field_service.portal_my_field_service_report_list', values)

    def _get_additional_intervention_data(self, intervention_sudo):
        return {
            'intervention_link_section': [],
        }

    @http.route('/my/field-service/<int:intervention_id>', type='http', auth='public', website=True)
    def portal_my_field_service_intervention(self, intervention_id, access_token=None, report_type=None, **kw):
        try:
            intervention_sudo = self._document_check_access('planning.slot', intervention_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if report_type in ('pdf', 'html', 'text'):
            return self._show_report(model=intervention_sudo, report_type=report_type, download=kw.get('download'), report_ref='planning_field_service.worksheet_custom')

        title = request.env._('Field Service Report - %s', format_datetime(request.env, intervention_sudo.start_datetime, dt_format='MMM d, YYYY', tz=request.env.tz or 'UTC', lang_code=get_lang(request.env).code))
        values = {
            'intervention_title': title,
            'page_name': 'field_service',
            'intervention': intervention_sudo,
            'user': request.env.user,
        }
        values.update(self._get_additional_intervention_data(intervention_sudo))
        values = self._get_page_view_values(intervention_sudo, None, values, 'my_field_service_history', False)
        return request.render('planning_field_service.portal_my_field_service_report_form', values)

    @http.route(['/my/field-service/<int:intervention_id>/sign'], type='jsonrpc', auth='public', website=True)
    def portal_sign_intervention(self, intervention_id, access_token=None, name=None, signature=None):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            intervention_sudo = self._document_check_access('planning.slot', intervention_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': request.env._('Invalid Intervention.')}
        if not intervention_sudo._can_show_sign_report_button():
            return {'error': request.env._('The intervention report is not in a state requiring customer signature.')}
        if not signature:
            return {'error': request.env._('Signature is missing.')}
        try:
            intervention_sudo.write({
                'worksheet_signature': signature,
                'worksheet_signed_by': name,
            })
        except (TypeError, binascii.Error):
            return {'error': request.env._('Invalid signature data.')}
        intervention_sudo.message_post_with_source(
            'planning_field_service.mail_template_data_intervention_report',
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
        )
        intervention_sudo._send_intervention_rating_mail()
        return {
            'force_refresh': True,
        }
