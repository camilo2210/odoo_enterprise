from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request
from odoo.tools import BinaryBytes

from odoo.addons.website.controllers import form


class WebsiteForm(form.WebsiteForm):

    def _handle_website_form(self, model_name, **kwargs):
        if model_name == 'planning.slot':
            if not request.env.website.company_id.website_planning_field_service:
                raise NotFound()
            # website_form_input_filter reads these from request.params to resolve the
            # partner; drop them here so they don't pollute the "Other Information" chatter log.
            for field_name in (
                'partner_name', 'partner_phone', 'partner_email', 'partner_company_name',
                'street', 'street2', 'city', 'zip', 'country_id', 'state_id',
            ):
                kwargs.pop(field_name, None)
        return super()._handle_website_form(model_name, **kwargs)

    def insert_attachment(self, model_sudo, id_record, files):
        if model_sudo.model != 'planning.slot' or not files:
            return super().insert_attachment(model_sudo, id_record, files)
        slot = model_sudo.env['planning.slot'].browse(id_record)
        request.env['ir.attachment'].sudo().create([{
            'name': file.filename,
            'raw': BinaryBytes(file.read()),
            'res_model': 'planning.slot',
            'res_id': slot.id,
        } for file in files])
        photos_line = slot.env._("%s photo(s) attached", len(files))
        slot.name = f"{slot.name.rstrip()}\n\n{photos_line}" if slot.name else photos_line


class WebsitePlanningFieldService(http.Controller):

    def _ensure_service_requests_enabled(self):
        if not request.env.website.company_id.website_planning_field_service:
            raise NotFound()

    def sitemap_service_requests(env, rule, qs):
        if env.website.company_id.website_planning_field_service and (not qs or qs.lower() in '/service-requests'):
            yield {'loc': '/service-requests'}

    @http.route('/service-requests', type='http', auth='public', website=True, sitemap=sitemap_service_requests)
    def service_requests(self, **kwargs):
        self._ensure_service_requests_enabled()
        return request.render('website_planning_field_service.service_requests')

    @http.route('/service-requests/submitted', type='http', auth='public', website=True, sitemap=False)
    def service_requests_submitted(self, **kwargs):
        self._ensure_service_requests_enabled()
        return request.render('website_planning_field_service.service_requests_submitted')

    @http.route('/service-requests/setup', type='jsonrpc', auth='public', methods=['POST'], website=True, readonly=True)
    def service_requests_setup(self):
        self._ensure_service_requests_enabled()

        prefill = {}
        if not (user := request.env.user)._is_public():
            prefill = {
                'country_id': user.country_id.id,
                'state_id': user.state_id.id,
            }
        return {
            'countries': request.env['res.country'].search_read([], ['id', 'name']),
            'planning_roles': request.env['planning.role'].sudo().search_read([], ['id', 'name']),
            'prefill': prefill,
            # Enable autocomplete if website_address_autocomplete is installed.
            'google_places_enabled': (
                hasattr(request.env.website, 'has_google_places_api_key')
                and request.env.website.has_google_places_api_key()
            ),
        }
