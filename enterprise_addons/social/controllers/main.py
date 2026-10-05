# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from werkzeug.exceptions import BadRequest, Forbidden, NotFound
from werkzeug.urls import url_encode

from odoo import http, _
from odoo.http.requestlib import fragment_to_query_string
from odoo.exceptions import MissingError
from odoo.http import request
from odoo.tools import plaintext2html
from odoo.tools.misc import consteq

_logger = logging.getLogger(__name__)


class SocialValidationException(Exception):
    def __init__(self, message, documentation_link=False, documentation_link_label=False, documentation_link_icon_class=False):
        """This custom exception allow us to show either a plain text error message or a error message with a redirect link
        to the documentation.
        : param str message: error message to be shown to the end-user.
        : param str documentation_link: allows us to put a link to the documentation of respective social media.
        : param str documentation_link_label: a label to be shown to the end-user of the documentation_link.
        : param str documentation_link_icon_class: font-awsome icon class of the respective social media.
        """
        self.message = message
        self.documentation_link = documentation_link
        self.documentation_link_label = documentation_link_label
        self.documentation_link_icon_class = documentation_link_icon_class
        super().__init__(message)

    def get_message(self):
        return plaintext2html(self.message)

    def get_documentation_data(self):
        return {
            'documentation_link': self.documentation_link,
            'documentation_link_label': self.documentation_link_label,
            'documentation_link_icon_class': self.documentation_link_icon_class,
        }

class SocialController(http.Controller):

    @http.route('/social/download_attachment/<int:attachment_id>/<string:filename>', type='http', auth='public')
    def social_download_social_attachment(self, attachment_id, filename, token):
        """Route used by the social API to download attachments (eg: when sending attachment in direct messages).

        The <filename> segment is not used to find the attachment, it is only
        there because the social media name the file they download after the
        last segment of the URL.
        """
        if not token:
            raise BadRequest()

        attachment_sudo = self.env['ir.attachment'].browse(attachment_id).sudo().exists()
        if (
            not attachment_sudo
            or not (expected := self.env['social.account']._get_attachment_token(attachment_sudo))
            or not consteq(token, expected)
        ):
            raise NotFound()

        return attachment_sudo._to_http_stream().get_response(as_attachment=True)

    def _get_social_stream_post(self, stream_post_id, media_type):
        """ Small utility method that fetches the post and checks it belongs
        to the correct media_type """
        stream_post = request.env['social.stream.post'].search([
            ('id', '=', stream_post_id),
            ('stream_id.account_id.media_id.media_type', '=', media_type),
        ])
        if not stream_post:
            raise MissingError(_("Uh-oh! It looks like this message has been deleted from X."))

        return stream_post

    @http.route('/social/<media>/start_auth_process', type='http', auth='user')
    @fragment_to_query_string(ignore={"media"})
    def social_start_auth_process(self, media, **kw):
        """Show an animation while we get the token from the social media.

        We cannot add the media in GET parameter because some social medias
        (like LinkedIn) will build the URL `/social/loading?redirect=/social_xxx/callback?arg=...`
        (with 2 `?`). So we include the media type in the URL path.

        The browser will keep our page until the next one is processed, and so our
        animation stay in the browser until the authentication process is done or
        failed.
        """
        if not request.env["social.media"].search([('media_type', '=', media)]):
            raise Forbidden()

        return request.render(
            'social.social_http_authentication_redirect',
            {'redirect': f"/social_{media}/callback?{url_encode(kw)}"},
        )

    def _set_message_reaction(self, social_account, mail_guest, emoji, message_id):
        """The social user reacted with an emoji on one of our message (or removed a reaction)."""
        discuss_channel = next((
            c for c in mail_guest.channel_ids
            if c.livechat_social_account_id == social_account
        ), None)
        if not discuss_channel:
            return

        message = self.env["mail.message"].sudo().search([
            ("message_id", "=", message_id),
            ("model", "=", "discuss.channel"),
            ("res_id", "=", discuss_channel.id),
        ], limit=1)

        if not message:
            _logger.error("Social: failed to react to message %s", message_id)
            return

        _logger.info("Social: react to message %s with %s", message_id, emoji)

        if emoji:
            # remove the previous reactions
            reactions = self.env["mail.message.reaction"].sudo().search([
                ("message_id", "=", message.id),
                ("partner_id", "=", False),
                ("guest_id", "=", mail_guest.id),
            ])
            for reaction in reactions:
                message._message_reaction(reaction.content, "remove", self.env["res.partner"], mail_guest)

        message._message_reaction(
            emoji,
            "add" if emoji else "remove",
            self.env["res.partner"],
            mail_guest,
        )

    def _should_ignore_message_id(self, social_account, mail_guest, message_id):
        """Ensure that messages are processed only once.

        If the connection is too slow or failed, the social media API
        can re-call our endpoint many times. This can cause issues like
        sending many times the same answer on the social media for AI,
        creating many times the same mail message, etc.
        """
        mail_message_exists = self.env['mail.message'].sudo().search_count([
            ('message_id', '=', message_id),
            ('model', '=', 'discuss.channel'),
            ('res_id', 'in', mail_guest.channel_ids.ids)
        ], limit=1)
        if mail_message_exists:
            _logger.warning("Social: message id already exists")
            return True

        # check if another transaction is already processing the same message_id
        if not social_account._social_try_lock_message_id(message_id):
            _logger.warning("Social: concurrent transactions try to create the same message")
            return True
        return False

    def _process_livechat_message(
        self,
        social_account,
        mail_guest,
        message_id,
        message_body,
        reply_to_message_id,
        attachments,
    ):
        """Process an incoming social message.

        :param social_account: Social account that receive the message
        :param mail_guest: Mail guest corresponding to the author of
            the message
        :param message_id: Identifier of the social message
        :param message_body: Markup of the body
        :param reply_to_message_id: Identifier of the message we are replying to
        :param attachments: Attachments linked to the message
        """
        if self._should_ignore_message_id(social_account, mail_guest, message_id):
            return

        su_env = self.env(context={"guest": mail_guest}, su=True)
        livechat_channel = social_account.livechat_channel_id.with_env(su_env)

        discuss_channel = next((
            c.with_env(su_env) for c in mail_guest.sudo().channel_ids
            if c.livechat_social_account_id == social_account
        ), None)

        send_away_message = False
        if (
            not discuss_channel
            or discuss_channel.livechat_end_dt
            or not discuss_channel.livechat_agent_partner_ids.user_ids
        ):
            # New conversation
            discuss_channel, send_away_message = self._init_discuss_channel(
                discuss_channel, livechat_channel, social_account, message_id, su_env)

        parent_message_id = None
        if reply_to_message_id:
            parent_message_id = su_env['mail.message'].search(
                [('message_id', '=', reply_to_message_id)], limit=1).id

        message = discuss_channel.message_post(
            body=message_body,
            message_id=message_id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            parent_id=parent_message_id,
            attachments=attachments,
        )

        livechat_channel._social_livechat_on_media_message(discuss_channel, message)

        if send_away_message:
            discuss_channel.with_user(self.env.ref('base.user_root')).message_post(
                body=livechat_channel.social_away_message,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    def _init_discuss_channel(self, discuss_channel, livechat_channel, social_account, message_id, su_env):
        """Initialize the discuss channel for the social live chat.

        :param discuss_channel: The discuss channel to re-use (if any)
        :param livechat_channel: The live channel
        :param social_account: The social account that received the message
        :param message_id: The identifier of the message (provided by the API)
        :param su_env: The env to use
        """
        previous_operator_id = False
        if discuss_channel and discuss_channel.livechat_agent_partner_ids:
            # for existing channel that have been closed, try to get the previous operator if possible
            previous_operator_id = discuss_channel.livechat_agent_partner_ids[0].id

        session_args = livechat_channel._social_get_session_args(previous_operator_id=previous_operator_id)
        operator_info = livechat_channel._get_operator_info(
            country_id=False,
            lang=False,
            chatbot_script_id=False,
            previous_operator_id=previous_operator_id,
            **session_args,
        )

        channel_vals = {
            **livechat_channel._get_livechat_discuss_channel_vals(
                **operator_info, livechat_social_account=social_account
            ),
            **su_env['discuss.channel']._process_extra_channel_params(**session_args)[1],
            'livechat_social_account_id': social_account.id,
            'livechat_failure': False,  # reset the old failure
        }

        if not operator_info['operator_partner']:
            channel_vals['livechat_failure'] = 'no_agent'

        if discuss_channel:
            # re-open the existing channel to not re-load all messages
            # first re-reset all previous members
            discuss_channel.channel_member_ids = False
            channel_vals['livechat_end_dt'] = False
            discuss_channel.write(channel_vals)
        else:
            discuss_channel = su_env['discuss.channel'].create(channel_vals)
            # Fetch the previous 1000 messages
            discuss_channel._fetch_social_messages(1000, message_id)

        if discuss_channel.message_ids:
            for member in discuss_channel.channel_member_ids:
                member._mark_as_read(max(discuss_channel.message_ids.ids))

        if agents := discuss_channel.livechat_agent_partner_ids.user_ids:
            discuss_channel._broadcast(agents)

        send_away_message = not operator_info['operator_partner'] and (livechat_channel.social_away_message or '').strip()
        return discuss_channel, send_away_message
