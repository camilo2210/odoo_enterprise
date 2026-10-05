# -*- coding: utf-8 -*-

import copy
import logging as logger
import re
import urllib.parse

from odoo import models, api, tools
from odoo.addons.iap.tools.iap_tools import iap_jsonrpc

_logger = logger.getLogger(__name__)

BLACK_LIST_PARAM = {
    'access_token',
    'auth_signup_token',
}


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, **kwargs):
        # Main notification method. Override to add support of sending OCN notifications.
        scheduled_date = self._is_notification_scheduled(kwargs.get('scheduled_date'))
        recipients_data = super()._notify_thread(message, **kwargs)

        # if scheduled for later: notification queue will call the notification method
        if not scheduled_date:
            self._notify_thread_by_ocn(message, recipients_data, **kwargs)
        return recipients_data

    def _notify_thread_by_ocn(self, message, recipients_data, **kwargs):
        """ Method to send cloud notifications for every mentions of a partner
        and every direct message. We have to take into account the risk of
        duplicated notifications in case of a mention in a channel of `chat` type.

        :param record message: <mail.message> record being notified.
        :param list recipients_data: list of recipients data based on <res.partner>
          records formatted like a list of dicts containing information. See
          ``MailThread._notify_get_recipients()``;

        """
        icp_sudo = self.env['ir.config_parameter'].sudo()
        # Avoid to send notification if this feature is disabled or if no user use the mobile app.
        if not icp_sudo.get_str('odoo_ocn.project_id') or not icp_sudo.get_bool('mail_mobile.enable_ocn'):
            return

        pids = self._notify_get_recipients_for_extra_notifications(message, recipients_data)
        if not pids:
            return

        self._notify_by_ocn_send(message, pids, **kwargs)

    def _notify_by_ocn_send(self, message, partner_ids, **kwargs):
        """ Send the notification to a list of partners

        :param message: current mail.message record
        :param partner_ids: list of partner IDs
        """
        if not partner_ids:
            return
        receiver_ids = self.env['res.partner'].sudo().search([
            ('id', 'in', partner_ids),
            ('ocn_token', '!=', False)
        ])
        if receiver_ids:
            endpoint = self.env['res.config.settings']._get_endpoint()
            payload = self._notify_by_ocn_prepare_payload(message, receiver_ids, force_record_name=kwargs.get('force_record_name', False))

            # prepare chunks
            chunks = []
            at_mention_ocn_token_list = []
            identities_ocn_token_list = []
            at_mention_analyser_id_list = self._at_mention_analyser(message.body)
            for receiver_id in receiver_ids:
                if receiver_id.id in at_mention_analyser_id_list:
                    at_mention_ocn_token_list.append(receiver_id.ocn_token)
                else:
                    identities_ocn_token_list.append(receiver_id.ocn_token)

            # first chunk
            if identities_ocn_token_list:
                chunks.append({
                    'ocn_tokens': identities_ocn_token_list,
                    'data': payload,
                })

            # second chunk for mentions with specific channel
            if at_mention_ocn_token_list:
                new_payload = copy.copy(payload)
                new_payload['android_channel_id'] = 'AtMention'
                chunks.append({
                    'ocn_tokens': at_mention_ocn_token_list,
                    'data': new_payload,
                })

            for chunk in chunks:
                try:
                    iap_jsonrpc(endpoint + '/iap/ocn/send', params=chunk)
                except Exception as e:
                    _logger.error('An error occurred while contacting the ocn server: %s', e)

    def _notify_by_ocn_prepare_payload(self, message, receiver_ids, force_record_name=False):
        """Returns dictionary containing message information for mobile device.
        This info will be delivered to mobile device via Google Firebase Cloud
        Messaging (FCM). And it is having limit of 4000 bytes (4kb)
        """
        payload = {
            "android_channel_id": "Following",
            "author_name": message.author_id.name,
            "model": message.model,
            "res_id": message.res_id,
            "db_id": self.env['res.config.settings']._get_ocn_uuid(),
            "subject": force_record_name or message.record_name or message.subject
        }

        body = message.body
        # Check payload limit of 4000 bytes (4kb) and if remain space add the body
        payload_length = len(str(payload).encode('utf-8'))
        # FIXME: when msg_type is 'user_notification', the type value of msg_vals.get('body') is bytes
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        if payload_length < 4000:
            payload_body = tools.html2plaintext(body)
            payload['body'] = payload_body[:4000 - payload_length]

        return payload

    @api.model
    def _at_mention_analyser(self, body):
        """
        Analyse the message to see if there is a @Mention in the notification
        :param body: original body of current mail.message record
        :return: a array with the list of ids for the @Mention partners
        """
        if isinstance(body, bytes):
            body = body.decode('utf-8')

        at_mention_ids = []
        regex = r"<a[^>]+data-oe-id=[\'\"](?P<id>\d+)[\'\"][^>]+data-oe-model=[\'\"](?P<model>[\w.]+)['\"][^>]?>@[^<]+<\/a>"
        matches = re.finditer(regex, body)

        for match in matches:
            if match.group('model') == 'res.partner':
                match_id = match.group('id')
                try:
                    at_mention_ids.append(int(match_id))
                except (ValueError, TypeError):
                    # We catch the exception because mail.message is mainly used by other app.
                    # So it's better to have no id instead of blocking the process.
                    _logger.error("Invalid conversion to int: %s" % match_id)
        return at_mention_ids

    # Redirect URL

    def _notify_get_action_link(self, link_type, model=False, res_id=False, **kwargs):
        original_link = super()._notify_get_action_link(link_type, model=model, res_id=res_id, **kwargs)
        # BLACK_LIST_PARAM to avoid leak of token
        if link_type != 'view' or BLACK_LIST_PARAM.intersection(kwargs.keys()):
            return original_link

        # Check if feature is enable to avoid request and computation
        disable_redirect_fdl = self.env['ir.config_parameter'].sudo().get_bool(
            'mail_mobile.disable_redirect_firebase_dynamic_link')
        if disable_redirect_fdl:
            return original_link

        # Force to have absolute url and not relative url
        # This is already done in the super function _notify_get_action_link
        # but in some case "this" is not defined.
        # The base url is not prepend it's why we do it manually.
        if original_link.startswith('/'):
            base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url')
            original_link = base_url + original_link

        url_params = urllib.parse.urlencode({
            'link': original_link,
        })
        return "%s?%s" % ('https://redirect-url.email/', url_params)
