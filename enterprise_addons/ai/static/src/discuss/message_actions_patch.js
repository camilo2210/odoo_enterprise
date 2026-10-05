import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { registerMessageAction, MessageAction } from "@mail/core/common/message_actions";
import { unwrapContents } from "@html_editor/utils/dom";
import { setElementContent } from "@web/core/utils/html";

export const AIMessageActions = [
    "insertToComposer",
    "copy-message",
    "send-message-direct",
    "log-note-direct",
    "media_dialog_use_this",
    "regenerate_image",
];

registerMessageAction("insertToComposer", {
    condition: ({ channel, message, store }) =>
        !!channel?.aiSpecialActions?.insert &&
        store.aiInsertButtonTarget && // after a reload both parts of the below conditions are undefined and but we don't want to button to appear
        (store.aiInsertButtonTarget === channel.aiChatSource || store.env.services.ui.isSmall) &&
        !message.isSelfAuthored,
    name: _t("Use this"),
    onSelected: ({ channel, message, store }) => {
        const targetElementSelection = channel.aiSpecialActions.selectPreviousInsertion(
            channel.textSelection?.selectionId
        );
        const fragment = document.createDocumentFragment();
        const content_root = document.createElement("span");
        content_root.setAttribute("data-ai-selection-id", channel.textSelection?.selectionId);
        setElementContent(content_root, message.body);
        // check if the content is enclosed in a <p> element, if so, unwrap it
        const paragraphElements = content_root.querySelectorAll("p");
        if (paragraphElements.length === 1) {
            unwrapContents(paragraphElements[0]);
        }
        fragment.appendChild(content_root);

        channel.aiSpecialActions.insert(fragment, targetElementSelection);

        if (store.env.services.ui.isSmall) {
            channel.closeChatWindow();
        }
    },
    sequence: 10,
});
registerMessageAction("send-message-direct", {
    condition: ({ channel, message }) =>
        !!channel?.aiSpecialActions?.sendMessage && !message.isSelfAuthored && message.isDiscussion, // don't show the buttons for the user's messages,
    name: _t("Send as Message"),
    onSelected: ({ channel, message }) => channel.aiSpecialActions.sendMessage(message),
    sequence: 20,
});
registerMessageAction("log-note-direct", {
    condition: ({ channel, message }) =>
        !!channel?.aiSpecialActions?.logNote && !message.isSelfAuthored && message.isDiscussion, // don't show the buttons for the user's messages
    name: _t("Log as Note"),
    onSelected: ({ channel, message }) => channel.aiSpecialActions.logNote(message),
    sequence: 25,
});

registerMessageAction("media_dialog_use_this", {
    condition: ({ channel, message }) =>
        !!channel?.aiSpecialActions?.useThis &&
        !message.isSelfAuthored &&
        !!message.attachment_ids.filter((attachment) => attachment.mimetype.includes("image"))
            .length,
    name: _t("Use This"),
    onSelected: ({ channel, ...args }) => {
        channel.aiSpecialActions.useThis({ channel, ...args });
    },
    sequence: 10,
});

registerMessageAction("regenerate_image", {
    condition: ({ channel, message }) =>
        !message.isSelfAuthored &&
        message.eq(channel?.newestMessage) &&
        !!message.attachment_ids.filter(
            (attachment) =>
                attachment.mimetype.includes("image") && attachment.name.includes("AI Generated")
        ).length,
    icon: "refresh",
    name: _t("Try again"),
    onSelected: ({ channel }) => {
        channel.post("Try again", {}, { ai_prompt_button_ref: "ai.ai_prompt_regenerate_image" });
    },
    sequence: 15,
});

patch(MessageAction.prototype, {
    _condition({ channel, message }) {
        if (channel?.isAiChat) {
            if (
                (message.bodyEl?.querySelector(".ai_user_input_request") &&
                    this.id !== "copy-message") ||
                !AIMessageActions.includes(this.id)
            ) {
                return false;
            }
            if (this.id === "copy-message") {
                return message.isDiscussion || message.isNote;
            }
        }
        return super._condition(...arguments);
    },
    _sequence({ channel }) {
        if (this.id === "copy-message" && channel?.isAiChat) {
            return 50;
        }
        return super._sequence(...arguments);
    },
});
