import { mailModels } from "@mail/../tests/mail_test_helpers";

export class MailThread extends mailModels.MailThread {
    /** @override */
    _store_thread_fields(res) {
        /** @type {import("mock_models").WhatsAppTemplate} */
        const WhatsAppTemplate = this.env["whatsapp.template"];

        super._store_thread_fields(...arguments);
        const can_send_whatsapp =
            WhatsAppTemplate.search_count([
                ["model", "=", this._name],
                ["status", "=", "approved"],
            ]) > 0;
        res.attr("canSendWhatsapp", can_send_whatsapp);
    }
}
