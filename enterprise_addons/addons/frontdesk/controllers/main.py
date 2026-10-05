# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, fields, release
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.http import request
from odoo.http.session import logout
from odoo.tools import consteq
from odoo.tools.image import image_data_uri

class Frontdesk(http.Controller):
    def _get_additional_info(self, frontdesk, lang, is_mobile=False):
        logout(request.session, keep_db=True)
        return request.render('frontdesk.frontdesk', {
            'frontdesk': frontdesk,
            'is_mobile': is_mobile,
            'current_lang': lang,
            'session_info': {
                'server_version': release.version,
                'server_version_info': release.version_info,
                'user_context': {'lang': lang},
            }
        })

    def _verify_token(self, frontdesk, token):
        if consteq(frontdesk.access_token, token):
            return True
        else:
            time_difference = fields.Datetime.now() - fields.Datetime.from_string(token[-19:])
            if time_difference.total_seconds() <= 3600 and consteq(frontdesk._get_tmp_code(), token[:64]):
                return True
            return False

    @http.route('/kiosk/<int:frontdesk_id>/<string:token>', type='http', auth='public', website=True)
    def launch_frontdesk(self, frontdesk_id, token, lang='en_US'):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        return self._get_additional_info(frontdesk, lang)

    @http.route('/kiosk/<int:frontdesk_id>/mobile/<string:token>', type='http', auth='public', website=True)
    def launch_frontdesk_mobile(self, frontdesk_id, token, lang='en_US'):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.render('frontdesk.frontdesk_qr_expired', {
                'session_info': {
                    'server_version': release.version,
                    'server_version_info': release.version_info,
                }
            })
        return self._get_additional_info(frontdesk, lang, is_mobile=True)

    @http.route('/kiosk/<int:frontdesk_id>/get_tmp_code/<string:token>', type='jsonrpc', auth='public')
    def get_tmp_code(self, frontdesk_id, token):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        return (frontdesk._get_tmp_code(), fields.Datetime.to_string(fields.Datetime.now()))

    @http.route('/frontdesk/<int:frontdesk_id>/<string:token>/get_frontdesk_data', type='jsonrpc', auth='public')
    def get_frontdesk_data(self, frontdesk_id, token):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        return frontdesk._get_frontdesk_data()

    @http.route('/frontdesk/<int:frontdesk_id>/background', type='http', auth='public')
    def frontdesk_background_image(self, frontdesk_id):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.image:
            return ""
        return request.env['ir.binary']._get_image_stream_from(frontdesk, 'image').get_response()

    @http.route('/frontdesk/<int:frontdesk_id>/<string:token>/hosts_infos', type='jsonrpc', auth='public')
    def hosts_infos(self, frontdesk_id, token, limit, offset, domain):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        domain = Domain(domain)

        allowed_domain = {
            'department_id': ('=',),
            'display_name': ('ilike',),
        }
        for condition in domain.iter_conditions():
            if condition.operator not in allowed_domain.get(condition.field_expr, ()):
                raise UserError(self.env._(
                    "Invalid domain. Allowed filters are: department_id with '=' and display_name with 'ilike'.",
                ))

        base_domain = Domain([
            ('company_id', '=', frontdesk.company_id.id),
            '|',
                ('work_email', '!=', False),
                ('work_phone', '!=', False)
        ])
        if frontdesk.host_ids:
            base_domain = Domain.AND([base_domain, [('id', 'in', frontdesk.host_ids.ids)]])
        domain = Domain.AND([domain, base_domain])
        employees = request.env['hr.employee'].sudo().search_fetch(
            domain, ['id', 'display_name', 'job_id', 'avatar_128'],
            limit=limit, offset=offset, order="name, id"
        )
        employees_data = [{
            'id': employee.id,
            'display_name': employee.display_name,
            'job_id': employee.job_id.name,
            'avatar': image_data_uri(employee.avatar_128),
        } for employee in employees]
        return {
            'records': employees_data,
            'length': request.env['hr.employee'].sudo().search_count(domain)
        }

    @http.route('/frontdesk/<int:frontdesk_id>/<string:token>/get_departments', type='jsonrpc', auth='public')
    def get_departments(self, frontdesk_id, token):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        departments = request.env['hr.department'].sudo().search([('company_id', '=', frontdesk.company_id.id)])
        department_list = []
        for department in departments:
            employee_domain = Domain([
                ('department_id', '=', department.id),
                ('company_id', '=', frontdesk.company_id.id),
                '|',
                    ('work_email', '!=', False),
                    ('work_phone', '!=', False)
            ])
            if frontdesk.host_ids:
                employee_domain = Domain.AND([employee_domain, [('id', 'in', frontdesk.host_ids.ids)]])
            employee_count = request.env['hr.employee'].sudo().search_count(employee_domain)
            if employee_count:
                department_list.append({
                    'id': department.id,
                    'name': department.name,
                    'count': employee_count
                })
        return department_list

    @http.route('/frontdesk/<int:frontdesk_id>/<string:token>/prepare_visitor_data', type='jsonrpc', auth='public', methods=['POST'])
    def prepare_visitor_data(self, frontdesk_id, token, visitor_id=None, **kwargs):
        frontdesk = request.env['frontdesk.frontdesk'].sudo().browse(frontdesk_id)
        if not frontdesk.exists() or not self._verify_token(frontdesk, token):
            return request.not_found()
        visitor = request.env['frontdesk.visitor'].browse(visitor_id)
        vals = {'state': 'checked_in'}
        if visitor:
            return visitor.sudo().write(vals)
        else:
            vals.update({
                'station_id': frontdesk.id,
                'name': kwargs.get('name'),
                'phone': kwargs.get('phone'),
                'email': kwargs.get('email'),
                'check_in': fields.Datetime.now(),
                'company': kwargs.get('company'),
                'host_id': kwargs.get('host_id'),
            })
            visitor = request.env['frontdesk.visitor'].sudo().create(vals)
            return {'visitor_id': visitor.id}
