import { patch } from "@web/core/utils/patch";
import { SetCoverBackgroundAction } from "@website/builder/plugins/options/cover_properties_option_plugin";

patch(SetCoverBackgroundAction.prototype, {
    getMediaDialogProps({ editingElement }) {
        const props = super.getMediaDialogProps({ editingElement });
        const backgroundImageSrc =
            editingElement.querySelector(".o_record_cover_image")?.style.backgroundImage;
        const path = backgroundImageSrc?.match(/url\(["']?([^"']+)["']?\)/)?.[1];
        return {
            ...props,
            imageSrc: path,
        };
    },
});
