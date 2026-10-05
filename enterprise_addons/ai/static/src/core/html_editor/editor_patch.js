import { Editor } from "@html_editor/editor";
import { patch } from "@web/core/utils/patch";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";

patch(Editor.prototype, {
    destroy(willBeRemoved) {
        super.destroy(willBeRemoved);
        // get aiSpecialActions() of MediaDialog captures this (the media dialog instance) because of the lambda function
        // which indirectly makes the ai channel hold a reference to the editor. This reference is not updated once the editor
        // is destroyed. Thus, the UseThis action won't function properly and has to be dropped.
        aiChannelBus.trigger("AI: Drop UseThis Action");
    },
});
