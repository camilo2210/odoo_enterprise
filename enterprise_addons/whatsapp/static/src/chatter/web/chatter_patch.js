import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    sendWhatsapp() {
        const send = async (thread) => {
            await new Promise((resolve) => {
                this.env.services.action.doAction(
                    {
                        type: "ir.actions.act_window",
                        name: _t("Send WhatsApp Message"),
                        res_model: "whatsapp.composer",
                        view_mode: "form",
                        views: [[false, "form"]],
                        target: "new",
                        context: {
                            active_model: thread.model,
                            active_id: thread.id,
                        },
                    },
                    { onClose: resolve }
                );
            });
            if (thread === this.thread()) {
                thread.fetchNewMessages();
            }
        };
        if (this.thread().id) {
            send(this.thread());
        } else {
            this.onThreadCreated = send;
            this.webChatterProps.saveRecord?.();
        }
    },
});
