import { mailModels } from "@mail/../tests/mail_test_helpers";

export class MailMessage extends mailModels.MailMessage {
    /** @override */
    _store_message_fields(res) {
        /** @type {import("mock_models").WhatsAppMessage} */
        const WhatsAppMessage = this.env["whatsapp.message"];

        super._store_message_fields(...arguments);
        // sudo: whatsapp.message - can read the state of accessible messages
        res.attr(
            "whatsappStatus",
            (message) =>
                WhatsAppMessage.search_read([["mail_message_id", "=", message.id]])[0]?.state ??
                false,
            { predicate: (message) => message.message_type === "whatsapp_message" }
        );
    }
}
