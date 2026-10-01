import { mailModels } from "@mail/../tests/mail_test_helpers";

import { fields } from "@web/../tests/web_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;

const isWhatsAppChannel = (channel) => channel.channel_type === "whatsapp";

export class DiscussChannel extends mailModels.DiscussChannel {
    whatsapp_channel_blocked = fields.Boolean({ default: false });
    whatsapp_channel_valid_until = fields.Datetime({
        default: () => serializeDateTime(DateTime.local().plus({ days: 1 })),
    });
    wa_account_id = fields.Generic({ default: () => 1 });

    /** @override */
    _store_channel_fields(res) {
        super._store_channel_fields(res);
        res.one("group_public_id", ["full_name"], { predicate: isWhatsAppChannel });
        res.attr("whatsapp_channel_blocked", undefined, { predicate: isWhatsAppChannel });
        res.attr("whatsapp_channel_valid_until", undefined, { predicate: isWhatsAppChannel });
        res.one("whatsapp_partner_id", [], { predicate: isWhatsAppChannel });
        // sudo: discuss.channel - reading wa_account_id is allowed for multi-company users
        res.one("wa_account_id", ["name"], { predicate: isWhatsAppChannel, sudo: true });
    }

    /**
     * @override
     * @type {typeof mailModels.DiscussChannel["prototype"]["_types_allowing_seen_infos"]}
     */
    _types_allowing_seen_infos() {
        return super._types_allowing_seen_infos(...arguments).concat(["whatsapp"]);
    }
}
