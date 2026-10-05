import { Component, useProps, t } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";

export class ThumbnailItem extends Component {
    static template = "web_studio.ThumbnailItem";
    props = useProps({
        className: t.string().optional(),
        showMoreMenu: t.boolean().optional(true),
        icon: t.object(),
        onClick: t.function().optional(() => () => {}),
        canClick: t.boolean().optional(true),
        slots: t.any(),
    });
    static components = { Dropdown };

    get hasDropdown() {
        return this.props.showMoreMenu && this.props.slots && this.props.slots.dropdown;
    }
}
