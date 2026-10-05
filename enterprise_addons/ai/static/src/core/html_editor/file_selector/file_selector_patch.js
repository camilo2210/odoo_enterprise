import { patch } from "@web/core/utils/patch";
import { FileSelector } from "@html_editor/main/media/media_dialog/file_selector";

patch(FileSelector.prototype, {
    get isAIAllowed() {
        return false;
    },
});
