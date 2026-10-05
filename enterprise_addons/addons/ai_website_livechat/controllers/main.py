# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http, _
from odoo.http import request
from odoo.addons.mail.tools.discuss import add_guest_to_context, mail_route, Store


# Exceeding this per-render limit keeps the preview block as plain text links
# to avoid flooding the discuss UI with cards.
PREVIEW_MAX_CARDS = 25


class AIWebsiteLivechatController(http.Controller):

    @mail_route('/ai_website_livechat/create_chat_channel', methods=["POST"], type="jsonrpc", auth='public')
    def create_chat_channel_with_ai_agent(self, ai_agent_id):
        # Sudo => access is managed through _is_user_access_allowed.
        ai_agent = self.env['ai.agent'].sudo().search([('id', '=', ai_agent_id)])
        if not ai_agent or not ai_agent._is_user_access_allowed():
            return

        store = Store()
        guest = request.env['mail.guest']
        if request.env.user._is_public():
            guest = guest.sudo()._get_or_create_guest(
                guest_name=self._get_guest_name(),
                country_code=request.geoip.country_code,
                timezone=request.env["mail.guest"]._get_timezone_from_request(request),
            )
            ai_agent = ai_agent.with_context(guest=guest)
            request.update_context(guest=guest)
        if guest:
            store.add_global_values(guest_token=guest.sudo()._format_auth_cookie())
            # Existing chats are deleted and a new one is created to limit visitors to a single AI chat.
            # Not returning the active chat channel and creating a new one instead is a design choice.
            if active_channels := self.env['discuss.channel'].search([('is_member', '=', True), ('channel_type', '=', 'ai_chat')]):
                active_channels.sudo().unlink()
        channel = ai_agent._create_ai_chat_channel("AI livechat")
        self.env['ai.session'].sudo().create({
            'agent_id': ai_agent.id,
            'channel_id': channel.id,
        })
        store.add_global_values(request.env.user.sudo(False)._store_init_global_fields)
        store.add(channel, "_store_channel_fields")
        return {'channel_id': channel.id, 'store_data': store}

    def _get_guest_name(self):
        return _("Visitor")

    @http.route('/ai_website_livechat/is_livechat_operator_available', methods=["POST"], type="jsonrpc", auth='public')
    @add_guest_to_context
    def is_livechat_operator_available(self, livechat_channel_id):
        country = request.env['res.country']
        if not request.env.user._is_public():
            country = request.env.user.country_id
        elif request.geoip.country_code:
            country = request.env["res.country"].search(
                [("code", "=", request.geoip.country_code)], limit=1
            )
        # sudo() => visitor can access the livechat channel to check if there is an operator available
        livechat_channel = request.env['im_livechat.channel'].sudo().search([('id', '=', livechat_channel_id)])
        if not livechat_channel:
            return False
        operator = livechat_channel._get_operator(country_id=country.id, lang=request.cookies.get("frontend_lang"))
        operator = operator - self.env.user
        return bool(operator)

    @http.route('/ai/preview_cards', methods=["POST"], type="jsonrpc", auth='public', website=True)
    @add_guest_to_context
    def get_preview_cards(self, model, record_ids):
        # Don't attempt to render preview cards if there are too many
        # records, to avoid performance issues and flooding the UI with cards.
        if len(record_ids) > PREVIEW_MAX_CARDS:
            return {'html': False, 'count': 0}
        if not model or model not in request.env:
            return {'html': False, 'count': 0}
        model_obj = request.env[model]
        if not isinstance(model_obj, request.env.registry['ai.preview.card.mixin']):
            return {'html': False, 'count': 0}
        records = model_obj.search_fetch([('id', 'in', record_ids)])
        record_index = {record_id: index for index, record_id in enumerate(record_ids)}
        records = records.sorted(key=lambda record: record_index[record.id])
        result = records._ai_render_preview_cards()
        if not result:
            return {'html': False, 'count': 0}
        cards_html, card_count = result
        return {'html': cards_html, 'count': card_count}
