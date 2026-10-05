import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { render } from "@web/owl2/utils";
import { useBus } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

export class GroupMenu extends Component {
    static template = "mrp_mps.GroupMenu";
    static components = { CheckboxItem };

    setup() {
        useBus(this.env.model, "update", () => render(this));
    }

    get items() {
        return this.env.model.data.groups[0];
    }

    _toggle_group(group) {
        const value = {};
        value[group] = !this.items[group];
        this.env.model._saveCompanySettings(value);
    }

}
