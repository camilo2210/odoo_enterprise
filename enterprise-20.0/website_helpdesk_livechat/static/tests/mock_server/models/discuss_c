import { livechatModels } from "@im_livechat/../tests/livechat_test_helpers";

import { patch } from "@web/core/utils/patch";

patch(livechatModels.DiscussChannel.prototype, {
    _store_livechat_extra_fields(res) {
        /** @type {import("mock_models").HelpdeskTicket} */
        const HelpdeskTicket = this.env["helpdesk.ticket"];
        /** @type {import("mock_models").ResPartner} */
        const ResPartner = this.env["res.partner"];

        super._store_livechat_extra_fields(...arguments);
        res.many(
            "livechat_customer_partner_ids",
            (res) =>
                res.many("helpdesk_tickets", ["id", "name"], {
                    // mock: no partner hierarchy walk, and no team follower domain
                    value: (partner) =>
                        HelpdeskTicket.browse(
                            HelpdeskTicket.search([["partner_id", "=", partner.id]])
                        ),
                }),
            { value: (channel) => ResPartner.browse(this._livechat_customer_partner_ids(channel)) }
        );
    },
});
