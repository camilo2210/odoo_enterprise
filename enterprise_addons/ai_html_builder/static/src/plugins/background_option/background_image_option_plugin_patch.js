import { patch } from "@web/core/utils/patch";
import { ToggleBgImageAction, ReplaceBgImageAction } from "@html_builder/plugins/background_option/background_image_option_plugin";


patch(ToggleBgImageAction.prototype, {
    getMediaDialogProps(context) {
        const props = super.getMediaDialogProps(context);
        return {
            ...props,
            "media": context.editingElement,
        }
    }
});

patch(ReplaceBgImageAction.prototype, {
    getMediaDialogProps(context) {
        const props = super.getMediaDialogProps(context);
        return {
            ...props,
            "media": context.editingElement,
        }
    }
});
