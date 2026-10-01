import { MailComposerChatGPT } from "@ai/mail_composer_chatgpt";
import { registry } from "@web/core/registry";

/**
 * Override `interfaceKey` to `html_field_record`.
 * `sign.template` does not have `mail.thread`, which `mail_composer` requires.
 */
export class SignAIButton extends MailComposerChatGPT {
    static template = "mail.MailComposerChatGPT";

    get interfaceKey() {
        return "html_field_record";
    }
}

export const signAIButton = {
    component: SignAIButton,
    fieldDependencies: [{ name: "body", type: "html" }],
};

registry.category("fields").add("sign_ai_button", signAIButton);
