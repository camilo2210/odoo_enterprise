import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { fields } from "@mail/model/export";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").DiscussChannel} */
const discussChannelPatch = {
    setup() {
        super.setup();
        this.wa_account_id = fields.One("whatsapp.account");
        this.whatsapp_channel_blocked = undefined;
        this.whatsapp_channel_valid_until = fields.Datetime();
    },
    get importantCounter() {
        if (this.channel_type === "whatsapp") {
            return this.self_member_id?.message_unread_counter || this.message_needaction_counter;
        }
        return super.importantCounter;
    },
    get showImStatus() {
        return (this.channel_type === "whatsapp" && this.correspondent) || super.showImStatus;
    },
    get allowedToLeaveChannelTypes() {
        return [...super.allowedToLeaveChannelTypes, "whatsapp"];
    },
    get isAllowedToLeave() {
        if (this.channel_type !== "whatsapp") {
            return super.isAllowedToLeave;
        }
        const hasOtherAgent = this.channel_member_ids.some(
            (m) => m.notEq(this.whatsappMember) && m.notEq(this.self_member_id)
        );
        return super.isAllowedToLeave && hasOtherAgent;
    },
    async leaveChannel() {
        if (this.channel_type === "whatsapp") {
            await this.askLeaveConfirmation(
                _t(
                    "You are about to leave this whatsapp conversation and will no longer have access to it unless you are invited again. Are you sure you want to continue?"
                )
            );
        }
        return super.leaveChannel();
    },
};
patch(DiscussChannel.prototype, discussChannelPatch);
