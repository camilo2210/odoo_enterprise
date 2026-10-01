import { MediaDialog } from "@html_editor/main/media/media_dialog/media_dialog";
import { t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(MediaDialog.prototype, {
    setup() {
        super.setup();

        this.aiWebsiteSaleProps = useProps({
            fromShopExtraImage: t.boolean().optional(),
            reloadEditorAfterSave: t.boolean().optional(),
        });
    },
    async aiSaveAction() {
        await super.aiSaveAction(...arguments);
        if (this.aiWebsiteSaleProps.reloadEditorAfterSave) {
            this.env.bus.trigger("RELOAD_EDITOR");
        }
    },
    getMediaDialogData() {
        return Object.assign(super.getMediaDialogData(), {
            fromShopExtraImage: this.aiWebsiteSaleProps.fromShopExtraImage,
        });
    },
});
