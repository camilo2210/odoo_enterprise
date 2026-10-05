import { Component, computed, useProps, t } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { IconSelector } from "@html_editor/main/media/media_dialog/icon_selector";

export class StudioIconSelector extends Component {
    static template = "web_studio.StudioIconSelector";
    props = useProps({
        className: t.string().optional(""),
        value: t.string(),
        onSelect: t.function().optional(),
        required: t.boolean().optional(),
        slots: t.object().optional(),
    });
    static components = { Dropdown, IconSelector };
    required = computed(() => this.props.required ?? true);
    dropdown = useDropdownState();
    selectedMedia = computed(() => {
        if (!this.props.value) {
            return { icons: [] };
        }
        const filled = this.props.value.endsWith("_f");
        const dataIcon = filled
            ? this.props.value.slice(0, -2)
            : this.props.value;
        return {
            icons: [
                {
                    id: dataIcon,
                    name: dataIcon,
                    dataIcon,
                    source: dataIcon.startsWith("oi_") ? "oi" : "ms",
                    filled,
                },
            ],
        };
    });

    onIconSelect(media) {
        const { dataIcon, filled } = media;
        this.props.onSelect(`${dataIcon}${filled ? "_f" : ""}`);
        this.dropdown.close();
    }
}
