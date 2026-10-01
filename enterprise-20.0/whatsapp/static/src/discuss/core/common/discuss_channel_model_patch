import { fields } from "@mail/model/export";
import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { MEMBER_CATEGORIES } from "@mail/discuss/core/common/channel_member_list";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

MEMBER_CATEGORIES.push({
    sequence: 25,
    getMembers: (ch) => (ch.whatsappMember ? [ch.whatsappMember] : []),
    label: _t("WhatsApp User"),
    showCount: false,
});

/** @type {import("models").DiscussChannel} */
const discussChannelPatch = {
    setup() {
        super.setup(...arguments);
        this.whatsapp_partner_id = fields.One("res.partner");
        this.whatsappMember = this.computed(() => {
            if (this.channel_type !== "whatsapp") {
                return;
            }
            return this.channel_member_ids.find((member) =>
                member.partner_id?.eq(this.whatsapp_partner_id)
            );
        });
    },

    get chatChannelTypes() {
        return [...super.chatChannelTypes, "whatsapp"];
    },
    get memberListTypes() {
        return [...super.memberListTypes, "whatsapp"];
    },
    get allowedToRenameChannelTypes() {
        return [...super.allowedToRenameChannelTypes, "whatsapp"];
    },
    computeCorrespondent() {
        const correspondent = super.computeCorrespondent();
        if (this.channel_type === "whatsapp" && !correspondent) {
            return this.whatsappMember;
        }
        return correspondent;
    },
    _computeUnknownStatusMembers() {
        const res = super._computeUnknownStatusMembers();
        if (this.channel_type === "whatsapp") {
            return res.filter((member) => member.partner_id?.notEq(this.whatsapp_partner_id));
        }
        return res;
    },
};

patch(DiscussChannel.prototype, discussChannelPatch);
