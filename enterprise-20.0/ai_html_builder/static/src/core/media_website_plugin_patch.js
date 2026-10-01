import { patch } from "@web/core/utils/patch";
import { MediaWebsitePlugin } from "@html_builder/core/media_website_plugin";

patch(MediaWebsitePlugin.prototype, {
    getMediaDialogProps({ mediaEl, editableEl }) {
        const props = super.getMediaDialogProps({ mediaEl, editableEl });
        const { resModel, resId } = this.config.getRecordInfo
            ? this.config.getRecordInfo(editableEl)
            : {};
        return {
            ...props,
            originalRecordModel: resModel,
            originalRecordId: Number(resId),
        };
    },
});
