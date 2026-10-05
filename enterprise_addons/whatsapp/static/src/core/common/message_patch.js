import { Message } from "@mail/core/common/message";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    /**
     * @param {MouseEvent} ev
     */
    async onClick(ev) {
        const id = Number(ev.target.dataset.oeId);
        if (ev.target.closest(".o_whatsapp_channel_redirect")) {
            ev.preventDefault();
            let channel = await this.store["discuss.channel"].getOrFetch(id);
            if (!channel?.self_member_id) {
                await this.store.fetchStoreData("/discuss/channel/add_members", {
                    channel_id: id,
                    user_ids: [this.store.self_user.id],
                });
                channel = await this.store["discuss.channel"].getOrFetch(id);
            }
            channel.open();
            return;
        }
        super.onClick(ev);
    },

    getWhatsappStatusClass() {
        const statusClasses = {
            outgoing: "text-warning",
            sent: "text-success",
            delivered: "text-success",
            read: "text-success",
            replied: "text-success",
            received: "text-success",
            error: "text-danger",
            bounced: "text-danger",
            cancel: "text-danger",
        };
        return statusClasses[this.message.whatsappStatus] || "text-muted";
    },

    getWhatsappStatusTitle() {
        const statusTitles = {
            outgoing: _t("The message is being processed."),
            sent: _t("The message has been sent."),
            delivered: _t("The message has been successfully delivered."),
            read: _t("The message has been read by the recipient."),
            replied: _t("The recipient has replied to the message."),
            received: _t("The message has been successfully received."),
            error: _t("There was an issue sending this message."),
            bounced: _t("The message has been bounced."),
            cancel: _t("The message has been canceled."),
        };
        return (
            statusTitles[this.message.whatsappStatus] ||
            _t("The status of this message is currently unknown.")
        );
    },
});
