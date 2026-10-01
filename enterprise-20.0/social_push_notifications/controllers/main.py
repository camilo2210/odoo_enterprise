# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import http
from odoo.http import request
from odoo.tools import file_open


class SocialPushNotificationsController(http.Controller):
    @http.route('/social_push_notifications/service_worker.js', type='http', auth='public', methods=['GET'], readonly=True)
    def social_push_get_service_worker(self):
        path = 'social_push_notifications/static/src/service_worker.js'
        with file_open(path) as f:
            body = f.read()
        return request.make_response(body, [
            ('Content-Type', 'text/javascript'),
            ('Service-Worker-Allowed', '/')
        ])

    @http.route('/social_push_notifications/get_vapid_public_key', type='jsonrpc', auth='public', website=True)
    def social_push_get_vapid_public_key(self):
        """ Fetches the server public VAPID key. """
        vapid_public_key, _vapid_private_key = request.env['ir.config_parameter'].sudo()._get_vapid_keys()
        return vapid_public_key

    @http.route('/social_push_notifications/get_notification_request_config', type='http', auth='public', website=True, sitemap=False)
    def social_push_get_notification_request_config(self):
        """ Fetches the notification request config for the current website (if any). """
        config = {}
        if self.env.website.notification_request_title:
            config['title'] = self.env.website.notification_request_title
        if self.env.website.notification_request_body:
            config['body'] = self.env.website.notification_request_body
        if self.env.website.notification_request_delay:
            config['delay'] = self.env.website.notification_request_delay
        if self.env.website.notification_request_icon:
            config['icon'] = '/web/image/website/%s/notification_request_icon/48x48' % self.env.website.id

        return request.make_json_response(config, headers=[
            ('Cache-Control', f'public, max-age={60 * 60 * 24 * 7}')  # cache for 7 days
        ])

    @http.route('/social_push_notifications/save_push_subscription', type='jsonrpc', auth='public', website=True)
    def social_push_save_push_subscription(self, endpoint, keys):
        visitor_sudo = request.env['ir.http']._get_visitor_from_request(force_create=True)
        push_subscription = request.env['website.visitor.push.subscription'].sudo().search([
            ('endpoint', '=', endpoint)], limit=1)
        push_subscription_values = {
            'keys': json.dumps(keys),
            'website_visitor_id': visitor_sudo.id
        }
        if push_subscription:
            push_subscription.write(push_subscription_values)
        else:
            push_subscription.create({
                **push_subscription_values,
                'endpoint': endpoint
            })

    @http.route('/social_push_notifications/is_push_subscription_registered', type='jsonrpc', auth='public', website=True)
    def social_push_is_push_subscription_registered(self, endpoint, keys):
        visitor_sudo = request.env['ir.http']._get_visitor_from_request()
        if not visitor_sudo:
            return False
        return request.env['website.visitor.push.subscription'].sudo().search_count([
            ('endpoint', '=', endpoint),
            ('keys', '=', json.dumps(keys)),
            ('website_visitor_id', '=', visitor_sudo.id),
        ], limit=1) > 0

    @http.route('/social_push_notifications/social_post/<int:post_id>/push_notification_image', type='http', auth='public')
    def social_push_get_notification_image(self, post_id):
        social_post = request.env['social.post'].sudo().search([('id', '=', post_id), ('state', 'in', ['posting', 'posted'])], limit=1)
        return request.env['ir.binary']._get_image_stream_from(
            social_post, 'push_notification_image', width=64, height=64
        ).get_response()
