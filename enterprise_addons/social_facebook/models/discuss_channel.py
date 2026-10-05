# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

import requests
from markupsafe import Markup

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import plaintext2html
from odoo.tools.mail import is_html_empty
from odoo.tools.osutil import clean_filename
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    META_API_MESSAGES_MAX_LIMIT = 500

    def message_post(self, **kwargs):
        """Split the text message and the attachments in 2 messages.

        On Facebook, attachment and text are sent in 2 different messages
        so we need to create 2 mail messages to make the "reply to" or
        the "reaction" works properly.
        """
        if (
            (body := kwargs.get('body'))
            and not is_html_empty(body)
            and kwargs.get('attachment_ids')
            and (guest := self._social_get_mail_guest_recipient(**kwargs))
            and guest.meta_user_id
        ):
            kwargs_attachments = kwargs.copy()
            kwargs.pop('attachment_ids', None)
            kwargs_attachments.pop('body', None)
            super().message_post(**kwargs_attachments)

        return super().message_post(**kwargs)

    def _send_social_message(self, body, mail_guest, parent_message_id, attachment_ids):
        if self.livechat_social_account_id._is_meta_account() and (body or attachment_ids):
            if body and attachment_ids:
                raise UserError(self.env._("You cannot send a text message and attachments at the same time."))

            data = {
                "recipient": {"id": mail_guest.meta_user_id},
                "messaging_type": "RESPONSE",
                "message": {},
            }
            if parent_message_id:
                data["reply_to"] = {"mid": parent_message_id}

            if body:
                data["message"]["text"] = body
            else:
                attachments = self.env['ir.attachment'].browse(attachment_ids or ())
                if not all(a.get_base_url().startswith("https://") for a in attachments):
                    raise UserError(self.env._('Meta cannot download attachment from HTTP endpoint, update the web.base.url to use https.'))

                if len(attachments) == 1:
                    data["message"]["attachment"] = {
                        "type": (
                            "image" if attachments.mimetype.startswith("image/")
                            else "audio" if attachments.mimetype.startswith("audio/")
                            else "file"
                        ),
                        "payload": {"url": self._meta_attachment_url(attachments)},
                    }

                elif attachments and all(a.mimetype.startswith("image/") for a in attachments):
                    # we can send one file at a time, except for images
                    # see: https://developers.facebook.com/documentation/business-messaging/messenger-platform/send-messages
                    data["message"]["attachments"] = [{
                        "type": "image",
                        "payload": {"url": self._meta_attachment_url(attachment)},
                    } for attachment in attachments]

                elif attachments:
                    raise UserError(self.env._("You can upload many images at a time or only one file at a time."))

            response = requests.post(
                url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, "/me/messages"),
                params={"access_token": self.livechat_social_account_id._meta_access_token()},
                json=data,
                timeout=15,
            )
            if not response.ok:
                raise UserError(self.env._("Failed to send the message: %s", response.text))

            return response.json().get('message_id')

        return super()._send_social_message(body, mail_guest, parent_message_id, attachment_ids)

    def _meta_attachment_url(self, attachment):
        """Return the public URL from which Meta will download the attachment.

        The Send API has no field to name the file being sent, Meta names it
        after the last segment of the URL, so we end the URL with the filename.
        """
        self.ensure_one()
        return url_join(
            attachment.get_base_url(),
            f"/social/download_attachment/{attachment.id}/{quote(clean_filename(attachment.name), safe='')}"
            f"?token={self.livechat_social_account_id._get_attachment_token(attachment)}",
        )

    def _send_social_reaction(self, content, action, mail_guest, message_id):
        if self.livechat_social_account_id._is_meta_account():
            _logger.info("Social Meta: react to message %s with %s", message_id, content)
            data = {
                "recipient": {"id": mail_guest.meta_user_id},
                "payload": {"message_id": message_id}
            }
            if action == "add":
                data["sender_action"] = "react"
                data["payload"]["reaction"] = content
            else:
                data["sender_action"] = "unreact"

            response = requests.post(
                url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, "/me/messages"),
                params={"access_token": self.livechat_social_account_id._meta_access_token()},
                json=data,
                timeout=5,
            )
            if not response.ok:
                raise UserError(self.env._("Failed to react: %s", response.text))

        return super()._send_social_reaction(content, action, mail_guest, message_id)

    def _fetch_social_messages(self, to_fetch, ignore_message_id):
        social_account = self.livechat_social_account_id
        if social_account._is_meta_account():
            mail_guest = self.livechat_customer_guest_ids.filtered('meta_user_id')[:1]
            if not mail_guest:
                raise ValueError('The guest is not a meta user')

            response = requests.get(
                url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, "/me/conversations"),
                params={
                    "access_token": social_account._meta_access_token(),
                    "platform": self._get_meta_fetch_messages_platform(social_account.media_type),
                    "fields": "id,participants,updated_time",
                    "user_id": mail_guest.meta_user_id,
                },
                timeout=15,
            )
            if not response.ok:
                raise UserError(self.env._('Failed to fetch the conversations: %s', response.text))

            # skip group conversation
            conversation = next(
                (values for values in response.json().get('data', ())
                    if len(values['participants']['data']) == 2), None)
            if not conversation:
                raise UserError(self.env._('Failed to find the conversation: %s', response.text))

            endpoint = url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, f"/{conversation['id']}/messages")
            next_url = endpoint + "?" + urlencode({
                "access_token": social_account._meta_access_token(),
                "fields": "id,message,from,created_time,attachments,shares,sticker,reply_to",
                "limit": self.META_API_MESSAGES_MAX_LIMIT,
            })

            def _prepare_body(values):
                # Don't create attachments for all previous files in the discussion for performance reasons,
                # add the link of the file in the message instead
                attachments = values.get('attachments', {}).get('data') or ()
                lines = [plaintext2html(values['message'] or '')] if values.get('message') else []
                for attachment in attachments:
                    # image URLs are in `image_data`, audio / other file URLs are in `file_url`
                    url = attachment.get('image_data', {}).get('url') or attachment.get('file_url')
                    if not url or not url.startswith("https://"):
                        continue
                    if attachment.get('mime_type', '').startswith('image/'):
                        # sticker does not have a `preview_url`
                        preview_url = attachment.get('image_data', {}).get('preview_url') or url
                        lines.append(
                            Markup('<a class="o_social_livechat_attachment" href="%s" target="_blank"><img src="%s" title="%s"/></a>')
                            % (url, preview_url, attachment.get('name'))
                        )
                    else:
                        lines.append(
                            Markup('<a class="o_social_livechat_attachment" href="%s" target="_blank">%s</a>')
                            % (url, attachment.get('name') or self.env._('Unknown File'))
                        )

                if not lines:
                    return social_account._meta_get_unsupported_file_link()
                return Markup("<br>").join(lines)

            parent_ids_to_fix = {}  # map the message with their parent `message_id` if any
            to_create = []
            while next_url and len(to_create) < to_fetch:
                response = requests.get(next_url, timeout=25)
                if not response.ok:
                    raise UserError(self.env._('Failed to fetch the messages: %s', response.text))

                response_json = response.json()
                to_create.extend([{
                        'model': 'discuss.channel',
                        'res_id': self.id,
                        'body': _prepare_body(values),
                        'message_id': values['id'],
                        'author_id': False,  # force no author for history messages
                        'author_guest_id': mail_guest.meta_user_id == values['from']['id'] and mail_guest.id,
                        'date': datetime.strptime(values['created_time'], "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc).replace(tzinfo=None)
                    }
                    for values in response_json['data']
                    if values['id'] != ignore_message_id
                ])
                parent_ids_to_fix.update({
                    values['id']: parent_id
                    for values in response_json['data']
                    if (parent_id := values.get('reply_to', {}).get('mid'))
                })

                next_url = response_json.get('paging', {}).get('next')

            # the API returns the newest message first,
            # but we need their ids to follow the chronological order
            messages = self.env['mail.message'].create(list(reversed(to_create[:to_fetch])))
            _logger.debug("Social Meta: created %s messages", len(messages))

            # fix the `parent_id` field
            message_id_to_message = {message.message_id: message for message in messages}
            for message_id, parent_id in parent_ids_to_fix.items():
                if (child := message_id_to_message.get(message_id)) and (parent := message_id_to_message.get(parent_id)):
                    child.parent_id = parent

            return messages

        return super()._fetch_social_messages(to_fetch, ignore_message_id)

    def _get_meta_fetch_messages_platform(self, media_type):
        if media_type == "facebook":
            return "messenger"
