import { patch } from "@web/core/utils/patch";
import { ImageSelector } from "@html_editor/main/media/media_dialog/image_selector";

patch(ImageSelector.prototype, {
    get isAIAllowed() {
        return true;
    },
});
