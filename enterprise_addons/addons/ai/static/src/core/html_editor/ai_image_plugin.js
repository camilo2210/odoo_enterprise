import { Plugin } from "@html_editor/plugin";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { HISTORY_COMMIT_TYPES } from "@html_editor/core/history_plugin"
import { aiChannelDataRegistry } from "@ai/utils/ai_channel_data_registry";

export class AIImagePlugin extends Plugin {
    static id = "aiImage";
    static dependencies = ["selection"];

    resources = {
        on_history_commit_undone_handlers: (lastCommitUndone) =>
            this.restoreChannelImageToReplace(lastCommitUndone, HISTORY_COMMIT_TYPES.UNDO),
        on_history_commit_redone_handlers: (lastCommitRedone) =>
            this.restoreChannelImageToReplace(lastCommitRedone, HISTORY_COMMIT_TYPES.REDO),
        on_media_replaced_handlers: ({ newMediaEl }) =>
            this.updateChannelImageToReplace(newMediaEl),
        on_media_added_handlers: ({ newMediaEl }) =>
            this.updateChannelImageInsertionPosition(newMediaEl),
        on_will_save_handlers: async () => await this.markAttachmentsUsed(),
    };

    restoreChannelImageToReplace(lastCommitReversed, mode) {
        if (lastCommitReversed.data.currentTarget) {
            let targetEl = lastCommitReversed.data.currentTarget;
            const nextTarget = lastCommitReversed.data.nextTarget;
            if (!nextTarget) {
                return;
            }
            const aiChannelId = targetEl.dataset.aiChannelId || nextTarget.dataset.aiChannelId;
            if (mode === HISTORY_COMMIT_TYPES.REDO && (nextTarget || nextTarget === false)) {
                targetEl = nextTarget;
            }
            if (targetEl && aiChannelId) {
                aiChannelDataRegistry.setData(aiChannelId, "imageToReplace", targetEl);
            }
        }
    }

    updateChannelImageToReplace(newMediaEl) {
        if (!newMediaEl.dataset.aiChannelId) {
            return;
        }
        aiChannelDataRegistry.setData(newMediaEl.dataset.aiChannelId, "imageToReplace", newMediaEl);
    }

    updateChannelImageInsertionPosition(element) {
        if (!element.dataset.aiChannelId) {
            return;
        }
        aiChannelDataRegistry.setData(
            element.dataset.aiChannelId,
            "imageInsertionPosition",
            this.dependencies.selection.getEditableSelection()
        );
    }

    async markAttachmentsUsed() {
        // When the media dialog is used to add an attachment (image), a copy is created from that
        // attachment and the copy is used on the website. The copy has a reference `data-attachment-id`
        // to the original attachment. So, the original attachment should not be deleted.
        const editableEl = this.editable;
        const aiGeneratedImageElements = [...editableEl.querySelectorAll("[data-ai-channel-id]")];
        for (const element of aiGeneratedImageElements) {
            delete element.dataset.aiChannelId;
        }
        const attachmentIds = aiGeneratedImageElements.map((el) =>
            parseInt(el.dataset.attachmentId)
        );
        if (attachmentIds.length) {
            await this.services.orm.call("ai.attachment.vacuum", "mark_attachments_used", [], {
                attachment_ids: attachmentIds,
            });
        }
    }
}

MAIN_PLUGINS.push(AIImagePlugin);
