import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { Component, t, useProps } from "@odoo/owl";

export class GroupMenu extends Component {
    static template = "mrp_mps.GroupMenu";
    static components = { CheckboxItem };

    props = useProps({
        items: t.object(),
    });

    get items() {
        return this.props.items;
    }

    _toggle_group(group) {
        const value = {};
        value[group] = !this.props.items[group];
        this.env.model._saveCompanySettings(value);
    }

}
