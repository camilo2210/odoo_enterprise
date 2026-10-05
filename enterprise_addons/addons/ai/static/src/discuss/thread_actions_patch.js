import { ACTION_TAGS } from "@mail/core/common/action";
import {
    registerThreadAction,
    ThreadAction,
    threadActionsRegistry,
} from "@mail/core/common/thread_actions";
import {
    expandDiscussSequenceGroup,
    expandDiscussSequenceQuick,
} from "@mail/discuss/core/web/thread_actions";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

export const aiChatsActions = [
    "add-to-favorites",
    "close",
    "delete-ai-chat",
    "expand-discuss",
    "fold-chat-window",
    "remove-from-favorites",
    "rename-thread",
    "search-messages",
];

patch(ThreadAction.prototype, {
    // keep only actions that are relevant for ai chats
    _condition({ action, channel }) {
        if (channel?.isAiChat && !aiChatsActions.includes(action.id)) {
            return false;
        }
        return super._condition(...arguments);
    },
    computeCorrespondent() {
        const correspondent = super.computeCorrespondent();
        if (
            ["ai_composer", "ai_chat"].includes(this.channel_type) &&
            correspondent?.persona?.eq(this.store.self)
        ) {
            return undefined;
        }
        return correspondent;
    },
});

patch(threadActionsRegistry.get("expand-discuss"), {
    onSelected({ channel, store }) {
        // when expanding an ai chat, unfold the ai chats category and fold all the other ones
        if (channel?.isAiChat) {
            return store.env.services.action.doAction({
                context: { active_id: channel.id, expanded_from_ai_chat: true },
                type: "ir.actions.client",
                tag: "mail.action_discuss",
            });
        }
        return super.onSelected(...arguments);
    },
    sequenceGroup: ({ channel }) => (channel?.isAiChat ? 0 : expandDiscussSequenceGroup),
    sequenceQuick: ({ channel }) => (channel?.isAiChat ? 15 : expandDiscussSequenceQuick),
});

registerThreadAction("delete-ai-chat", {
    condition: ({ channel, owner }) => channel?.isAiChat && !owner.isDiscussContent,
    icon: "delete",
    name: _t("Delete AI chat"),
    onSelected: async ({ channel, store }) => {
        await channel.isLoadedPromise;
        if (!channel.hasLoadingFailed && channel.isEmpty) {
            return channel.deleteAiChatRpc();
        }
        store.env.services.dialog.add(ConfirmationDialog, {
            body: _t("Are you sure you want to delete this AI chat? All its content will be lost."),
            confirmLabel: _t("Delete AI chat"),
            confirm: () => channel.deleteAiChatRpc(),
            cancel: () => {},
        });
    },
    sequenceGroup: 20, // same as add-to-favorite
    tags: ACTION_TAGS.DANGER,
});
