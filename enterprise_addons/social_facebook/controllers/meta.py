# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import json
import logging
import requests
import urllib

from werkzeug.exceptions import Forbidden

from odoo.addons.social.controllers.main import SocialController
from odoo.http import request
from odoo.tools.misc import consteq
from odoo.tools import BinaryBytes, plaintext2html
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)


class SocialMetaController(SocialController):

    def _meta_verify_webhook(self, kwargs, webhook_verify_token):
        """Verify the webhook when adding the webhook URL in the meta application settings."""
        if kwargs.get('hub.mode') != 'subscribe':
            raise Forbidden()

        if not webhook_verify_token:
            _logger.error("Meta Webhook: verify token not configured in the settings")
            raise Forbidden()

        if not consteq(webhook_verify_token, kwargs.get('hub.verify_token', '')):
            _logger.error("Meta Webhook: invalid verify token")
            raise Forbidden()

        challenge = kwargs.get('hub.challenge', '')
        if not challenge.isdigit():
            raise Forbidden()

        return challenge

    def _meta_process_webhook(self, meta_user_account_field, meta_access_token_field, webhook_secret):
        """Process the webhook request we got from the meta API.

        Facebook and Instagram share the same API regarding webhook,
        and so the code is put in common here.
        """
        data = request.httprequest.data
        if webhook_secret:
            # Verify the Instagram signature that has been built with the application secret
            signature = bytes.fromhex(request.httprequest.headers.get('X-Hub-Signature-256', '').split('=')[-1])
        else:
            # Verify the signature from IAP that has been built with the shared secret
            webhook_secret = self.env['social.media']._get_webhook_shared_secret()
            signature = bytes.fromhex(request.httprequest.headers.get('Odoo-Signature-256', ''))

        expected = hmac.new(webhook_secret.encode(), data, hashlib.sha256).digest()
        if not signature or not consteq(signature, expected):
            _logger.error("Meta Webhook: invalid signature, %s", data)
            raise Forbidden()

        data = json.loads(data)

        for entry in data.get('entry', ()):
            meta_account_id = entry.get('id')
            social_account = self.env['social.account'].sudo().search(
                [(meta_user_account_field, '=', meta_account_id)], limit=1)
            if not meta_account_id or not social_account:
                _logger.warning("Meta Webhook: received notification for deleted account")
                continue

            if not social_account.livechat_channel_id:
                _logger.warning("Meta Webhook: no live channel for this account, disabling the webhook")
                social_account.action_delete_webhook()
                continue

            if messaging := entry.get('messaging'):
                self._process_messaging(messaging, social_account, meta_access_token_field, meta_account_id)

        return "ok"

    def _process_messaging(self, messaging, social_account, meta_access_token_field, meta_account_id):
        r_session = requests.Session()
        for message_values in messaging:
            sender_meta_id = message_values.get('sender', {}).get('id')
            if not sender_meta_id:
                _logger.info("Social Meta: received an invalid event: %s", message_values)
                continue
            if sender_meta_id == meta_account_id:
                # "message echoes", we get back a message we sent (from the social website or from Odoo)
                self._meta_handle_echo_message(social_account, message_values)
                continue

            mail_guest = self.env['mail.guest'].sudo().search([('meta_user_id', '=', sender_meta_id)], limit=1)
            if not mail_guest:
                response = r_session.get(
                    url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, sender_meta_id),
                    params={"access_token": social_account[meta_access_token_field]},
                    timeout=5,
                ).json()

                profile_picture = None
                if profile_picture_url := response.get('profile_pic'):
                    image_response = r_session.get(profile_picture_url, timeout=5)
                    if image_response.ok:
                        profile_picture = BinaryBytes(image_response.content)

                if response.get('name'):
                    name = response.get('name')
                elif (first_name := response.get('first_name')) and (last_name := response.get('last_name')):
                    name = f"{first_name} {last_name}"
                else:
                    _logger.error("Meta: failed to get the user's name: %s", response)
                    name = self.env._('Unknown user %s', sender_meta_id)
                if username := response.get('username'):
                    name = f'{name} ({username})'

                mail_guest = self.env['mail.guest'].sudo().create({
                    'name': name,
                    'image_1920': profile_picture,
                    'meta_user_id': sender_meta_id,
                })

            react_action = message_values.get('reaction', {}).get('action')
            if react_action in ("react", "unreact"):
                self._set_message_reaction(
                    social_account,
                    mail_guest,
                    message_values.get('reaction', {}).get('emoji', False),
                    message_values.get('reaction', {}).get('mid'),
                )
                continue

            attachments = []
            has_unsupported_file = False
            if attachment_values := message_values.get('message', {}).get('attachments'):
                done_urls = set()  # the sticker can be sent 2 times, once as image type, once as sticker type
                for value in attachment_values:
                    if value.get('type') == 'fallback':
                        # `fallback` is set when we send URLs (with no more information)
                        continue
                    if not value.get('payload', {}).get('url'):
                        _logger.debug("Social Meta: unsupported attachment: %s", value)
                        has_unsupported_file = True
                        continue
                    if value['payload']['url'] in done_urls:
                        continue
                    done_urls.add(value['payload']['url'])
                    response = r_session.get(value['payload']['url'], timeout=5)
                    if not response.ok:
                        _logger.error('Meta Webhook: failed to download the attachment, %s', response.text)
                        continue

                    attachments.append((
                        urllib.parse.urlsplit(value['payload']['url']).path.split('/')[-1],
                        response.content,
                        # create `discuss.voice.metadata` to render audio as vocal in discuss
                        {'voice': True} if value.get('type') == 'audio' else {}
                    ))

            message_body = plaintext2html(message_values.get('message', {}).get('text') or '')  # linkify URLs
            if has_unsupported_file or message_values.get('message', {}).get('is_unsupported'):
                # Some stickers are not supported
                message_body = social_account._meta_get_unsupported_file_link()

            self._process_livechat_message(
                social_account,
                mail_guest,
                message_values.get('message', {}).get('mid'),
                message_body,
                message_values.get('message', {}).get('reply_to', {}).get('mid'),
                attachments,
            )

            r_session.close()

    def _meta_handle_echo_message(self, social_account, message_values):
        """Called on `message_echoes`."""
        message_id = message_values.get('message', {}).get('mid')
        recipient_id = message_values.get('recipient', {}).get('id')
        if not message_id or not recipient_id:
            return

        mail_guest = self.env['mail.guest'].sudo().search(
            [('meta_user_id', '=', recipient_id)], limit=1)
        discuss_channel = next((
            c for c in mail_guest.sudo().channel_ids
            if c.livechat_social_account_id == social_account
        ), None)
        if not discuss_channel:
            _logger.info("Social Meta: received an echo for an unknown conversation")
            return
        message_exists = self.env['mail.message'].sudo().search_count([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', discuss_channel.id),
            ('message_id', '=', message_id),
        ], limit=1)
        # the lock is held by the transaction sending the message from Odoo
        # until its mail.message is committed
        if message_exists or not social_account._social_try_lock_message_id(message_id):
            _logger.debug("Social Meta: received an event for one of our own message, sent from Odoo")
        else:
            _logger.debug("Social Meta: received an event for one of our own message, sent from the social media")
            discuss_channel._social_on_self_sent_message()
