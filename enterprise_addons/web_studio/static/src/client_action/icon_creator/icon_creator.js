import { COLORS, BG_COLORS } from "@web_studio/utils";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { FileInput } from "@web/core/file_input/file_input";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { StudioIconSelector } from "@web_studio/client_action/components/icon_selector/icon_selector";

import { Component, useProps, t } from "@odoo/owl";
import { resizeBlobImg } from "@web/core/utils/files";

export const DEFAULT_ICON = {
    backgroundColor: BG_COLORS[0],
    color: COLORS[10],
    icon: "home",
    type: "custom_icon",
};

/**
 * Icon creator
 *
 * Component which purpose is to design an app icon. It can be an uploaded image
 * which will be displayed as is, or an icon customized with the help of presets
 * of colors and icon symbols (@see web_studio/static/src/utils for the full list
 * of colors).
 * @extends Component
 */
export class IconCreator extends Component {
    static components = {
        FileInput,
        StudioIconSelector,
        SelectMenu,
    };
    props = useProps({
        backgroundColor: t.string().optional(DEFAULT_ICON.backgroundColor),
        color: t.string().optional(DEFAULT_ICON.color),
        editable: t.boolean().optional(),
        icon: t.string().optional(DEFAULT_ICON.icon),
        type: t.selection(["base64", "custom_icon"]).optional(DEFAULT_ICON.type),
        uploaded_attachment_id: t.number().optional(),
        webIconData: t.string().optional(),
        onIconChange: t.function(),
    });
    static template = "web_studio.IconCreator";

    /**
     * @param {Object} [props]
     * @param {string} [props.backgroundColor] Background color of the custom
     *      icon.
     * @param {string} [props.color] Color of the custom icon.
     * @param {boolean} props.editable
     * @param {string} [props.icon] Material Symbols data-icon name of the
     *      custom icon, suffixed with "_f" for its filled variant.
     * @param {string} props.type 'base64' (if an actual image) or 'custom_icon'.
     * @param {number} [props.uploaded_attachment_id] Databse ID of an uploaded
     *      attachment
     * @param {string} [props.webIconData] Base64-encoded string representing
     *      the icon image.
     */
    setup() {
        this.orm = useService("orm");

        const onWillUploadFiles = async (fileList) =>
            Promise.all(
                fileList.map(async (file) => {
                    const blob = await resizeBlobImg(file, { height: 64, width: 64 });
                    return new File([blob], file.name);
                })
            );
        this.fileInputProps = {
            acceptedFileExtensions: "image/png",
            resModel: "res.users",
            resId: user.userId,
            onWillUploadFiles,
        };
    }

    get backgroundColorChoices() {
        return this.getChoices(BG_COLORS);
    }

    get colorChoices() {
        return this.getChoices(COLORS);
    }

    getChoices(object) {
        return object.map((color) => ({
            label: color,
            value: color,
        }));
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onDesignIconClick() {
        this.props.onIconChange(DEFAULT_ICON);
    }

    /**
     * @param {Object[]} files
     */
    async onFileUploaded([file]) {
        if (!file) {
            // Happens when cancelling upload
            return;
        }
        const res = await this.orm.read("ir.attachment", [file.id], ["raw"]);

        this.props.onIconChange({
            type: "base64",
            uploaded_attachment_id: file.id,
            webIconData: "data:image/png;base64," + res[0].raw.replace(/\s/g, ""),
        });
    }

    /**
     * @param {string} palette
     * @param {string} value
     */
    onPaletteItemClick(palette, value) {
        if (this.props[palette] === value) {
            return; // same value
        }
        this.props.onIconChange({
            backgroundColor: this.props.backgroundColor,
            color: this.props.color,
            icon: this.props.icon,
            type: "custom_icon",
            [palette]: value,
        });
    }
}
