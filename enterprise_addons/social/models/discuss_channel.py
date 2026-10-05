# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from lxml import etree, html
from markupsafe import Markup

from odoo import fields, models
from odoo.tools.mail import html_to_inner_content
from odoo.tools.mimetypes import get_extension
from odoo.tools.misc import limited_field_access_token


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    livechat_social_account_id = fields.Many2one("social.account", string="Social Account", ondelete="set null")

    def message_post(self, **kwargs):
        """When the social manager answer in a social channel, send the message on the social media."""
        if (
            kwargs.get('message_type') != 'notification'
            and (kwargs.get('body') or kwargs.get('attachment_ids'))
            and (guest := self._social_get_mail_guest_recipient(**kwargs))
        ):
            parent_message_id = None
            if parent_id := kwargs.get('parent_id'):
                parent_message_id = self.env['mail.message'].browse(parent_id).message_id

            kwargs['message_id'] = self._send_social_message(
                html_to_inner_content(kwargs.get('body') or ''),
                guest,
                parent_message_id,
                kwargs.get('attachment_ids'),
            )
            if kwargs['message_id']:
                # hold the lock until the `mail.message` is committed
                # (useful for "message sent from the social media website" detection
                # see @_meta_handle_echo_message)
                self.livechat_social_account_id._social_try_lock_message_id(kwargs['message_id'])

        return super().message_post(**kwargs)

    def _social_get_mail_guest_recipient(self, **message_values):
        """Return the guest if we should send the message on the social API."""
        self.ensure_one()
        if (
            self.livechat_channel_id
            and self.livechat_social_account_id
            and self._social_should_send_message(**message_values)
        ):
            return self.livechat_customer_guest_ids[:1]

    def _social_should_send_message(self, **message_values):
        guest = self.env["mail.guest"]._get_guest_from_context()
        if guest and guest not in self.livechat_customer_guest_ids:
            # we can invite external guests in the discussion
            return True
        return self.env.user._is_internal()

    def _send_social_message(self, body, mail_guest, parent_message_id, attachment_ids):
        """Send the message on the social media.

        Return the unique identifier of the message (created by the
        social media) that will be stored on the mail message.
        """
        self.ensure_one()

    def _send_social_reaction(self, content, action, mail_guest, message_id):
        self.ensure_one()

    def _fetch_social_messages(self, to_fetch, ignore_message_id):
        self.ensure_one()

    def _store_channel_fields(self, res):
        super()._store_channel_fields(res)
        res.one("livechat_social_account_id",
            lambda res: (res.attr("name"), res.one("media_id", ["id"])),
            sudo=True,
            predicate=lambda c: c.livechat_social_account_id)
        res.attr("livechat_failure", predicate=lambda c: c.livechat_social_account_id)
        res.many("livechat_customer_guest_ids", ["id"],
            sudo=True,
            predicate=lambda c: c.livechat_social_account_id)
        res.attr("social_account_image_url",
            lambda c: c._get_social_image_url(c.livechat_social_account_id.sudo()),
            predicate=lambda c: c.livechat_social_account_id)
        res.attr("social_account_media_image_url",
            lambda c: c._get_social_image_url(c.livechat_social_account_id.sudo().media_id),
            predicate=lambda c: c.livechat_social_account_id)

    def _get_social_image_url(self, record):
        """Return the URL to fetch the `image` of the given record.

        The access token allows the users and the guests, who
        have no read access on the social models (or even on the discuss channel
        for guest invited in the public view), to fetch the image.
        """
        token = limited_field_access_token(record, "image", scope="binary")
        return f"/web/image/{record._name}/{record.id}/image?access_token={token}"

    def _social_on_self_sent_message(self):
        """Called when we reply from the social media website.

        When we reply from the social media instead of from Odoo, that
        method is called in order to take actions (eg remove the AI
        agent from the channel).
        """
        self.ensure_one()

    def _get_channel_history_format_message(self, message, message_body, message_author, previous_message_author):
        """Format the message for a social livechat.

        Social live chat are special because there's no author for history
        messages, and the old messages attachments are not downloaded for
        performance reasons (used for the /lead command, etc).
        """
        attachments = []
        if self.livechat_social_account_id:
            if "o_social_livechat_attachment" in (message_body or ""):
                # history attachment are added as link in the message body
                # for performance reasons, take them out of the body to render
                # them like the attachments of the other messages
                body = html.fragment_fromstring(message_body, create_parent=True)
                links = body.xpath("//a[hasclass('o_social_livechat_attachment')]")
                attachments = [self._social_history_attachment_to_html(link) for link in links]
                for link in links:
                    link.drop_tree()
                message_body = Markup(etree.tostring(body, encoding="unicode"))

        return super()._get_channel_history_format_message(
            message, message_body, message_author, previous_message_author,
        ) + attachments

    def _get_channel_history_format_author(self, message_author):
        author_name = super()._get_channel_history_format_author(message_author)
        if not self.livechat_social_account_id:
            return author_name
        if not message_author:
            # history message have no author
            author_name = self.livechat_social_account_id.name
        elif message_author._name == "res.partner":
            author_name = f'{self.livechat_social_account_id.name} ({author_name})'
        return author_name

    def _social_history_attachment_to_html(self, link):
        """Render the attachment link of a history message like `_attachment_to_html`."""
        if (image := link.find("img")) is not None:
            return Markup(
                "<img src='%s' alt='%s' style='max-width: 75%%; height: auto; padding: 5px;'>"
            ) % (image.get("src"), image.get("title") or "")

        filename = link.text_content()
        return Markup(
            "<div data-embedded='file' data-oe-protected='true' contenteditable='false' data-embedded-props='%s'/>"
        ) % json.dumps({
            "fileData": {
                "extension": get_extension(filename).lstrip("."),
                "filename": filename,
                "url": link.get("href"),
            },
        })
