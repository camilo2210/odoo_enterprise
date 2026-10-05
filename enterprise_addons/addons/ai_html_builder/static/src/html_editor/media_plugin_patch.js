import { MediaPlugin } from "@html_editor/main/media/media_plugin";
import { patch } from "@web/core/utils/patch";

patch(MediaPlugin.prototype, {
    openMediaDialog(params = {}, editableEl = null) {
        // snippetModel is only added to the config of the editor by the html builder 
        params.openedFromHTMLBuilder = Boolean(this.config.snippetModel);
        return super.openMediaDialog(params, editableEl);
    },
});
