import { MediaPlugin } from "@html_editor/main/media/media_plugin";
import { patch } from "@web/core/utils/patch";
import { aiChannelDataRegistry } from "@ai/utils/ai_channel_data_registry";

patch(MediaPlugin.prototype, {
    openMediaDialog(params = {}, editableEl = null) {
        params.addHistoryStep = this.dependencies.history.commit;
        params.editorSelection = this.dependencies.selection.getEditableSelection();
        return super.openMediaDialog(params, editableEl);
    },

    async addMedia(element) {
        if (element.dataset.aiChannelId) {
            this.dependencies.selection.setSelection(
                aiChannelDataRegistry.getData(element.dataset.aiChannelId, "imageInsertionPosition")
            );
        }
        super.addMedia(element);
    },
});
