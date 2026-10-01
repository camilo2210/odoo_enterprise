import { getInnerHtml } from "@mail/utils/common/html";

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, onMounted, onWillUnmount, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { htmlJoin } from "@web/core/utils/html";

export class MailComposerChatGPT extends Component {
    static template = "mail.MailComposerChatGPT";
    props = useProps(standardFieldProps);

    setup() {
        this.store = useService("mail.store");
        this.orm = useService("orm");
        this.aiChatLauncher = useService("aiChatLauncher");
        let currentDialog, previousZIndex;
        onMounted(() => {
            currentDialog = document.querySelector(".o-overlay-item:has(.o_dialog");
            if (currentDialog) {
                previousZIndex = currentDialog.style.zIndex;
                // 1020 is the value of the $zindex-sticky which is the z-index value used for the `.o-mail-ChatWindow`
                // See odoo/addons/mail/static/src/core/common/chat_window.scss
                // We use this value to ensure that the dialog that contains this component is rendered below the `.o-mail-ChatWindow`s.
                currentDialog.style.zIndex = "1020";
            }
        });
        onWillUnmount(() => {
            this.store.aiInsertButtonTarget = false;
            if (currentDialog) {
                currentDialog.style.zIndex = previousZIndex;
            }
        });
    }

    async onOpenChatGPTPromptDialogBtnClick() {
        const resId = JSON.parse(this.props.record.data.res_ids || "[]")[0] || false;
        await this.aiChatLauncher.launchAIChat({
            interfaceKey: this.interfaceKey,
            recordModel: resId ? this.props.record.data.model : false,
            recordId: resId,
            originalRecordData: this.props.record.data,
            aiSpecialActions: {
                insert: (content) => {
                    const root = document.createElement("div");
                    root.appendChild(content);
                    const { body } = this.props.record.data;
                    this.props.record.update({ body: htmlJoin([getInnerHtml(root), body]) });
                },
                selectPreviousInsertion: (selectionId) => false,
            },
            channelTitle: this.props.record.data.subject,
            aiChatSourceId: this.props.record.id,
        });
    }

    // Getter so subclasses can override the key.
    get interfaceKey() {
        return "mail_composer";
    }
}

export const mailComposerChatGPT = {
    component: MailComposerChatGPT,
    fieldDependencies: [{ name: "body", type: "text" }],
};

registry.category("fields").add("mail_composer_chatgpt", mailComposerChatGPT);
