import { Component, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";

export class GenerateDropdown extends Component {
    static template = "l10n_be_hr_payroll.GenerateDropdown";
    static components = { Dropdown, DropdownItem };

    props = useProps(standardWidgetProps);

    setup() {
        this.action = useService("action");
    }

    get isDisabled() {
        return this.props.record.data.eligible_employee_count <= 0 || this.props.record.data.state === "canceled";
    }

    get isSecondary() {
        return this.props.record.data.state === "ready";
    }

    get isVisible() {
        return this.props.record.data.state !== "done";
    }

    async onAction(actionName) {
        await this.props.record.save()

        this.action.doActionButton({
            type: "object",
            name: actionName,
            resModel: this.props.record.resModel,
            resId: this.props.record.resId,
            resIds: this.props.record.resIds,
            context: this.props.record.context,
            onClose: () => this.props.record.load(),
        });
    }
}

export const generateDropdown = {
    component: GenerateDropdown,
};

registry.category("view_widgets").add("generate_dropdown", generateDropdown);
