/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { ViewButton } from "@web/views/view_button/view_button";

export class ActionableWarningsField extends Component {
    static template = "hr_payroll.ActionableWarnings";

    props = useProps(standardFieldProps);

    static components = { ViewButton };

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
    }

    async handleOnClick(warningData){
        return this.actionService.doAction(warningData.action, {
            onClose: (onCloseInfo) =>  {
                if (!onCloseInfo?.noReload) {
                    this.env.model.load();
                }
            }
        });
    }

    get inListView() {
        return this.env.config.viewType === "list";
    }

    get warningsByLevel() {
        const result = { danger: [], warning: [] };
        for (const [id, w] of Object.entries(this.props.record.data[this.props.name] || {})) {
            result[w.level].push({ ...w, id });
        }
        return result;
    }

    get displayedWarnings() {
        const all = [
            ...this.warningsByLevel.danger,
            ...this.warningsByLevel.warning,
        ];
        return this.inListView ? all.slice(0, 1) : all;
    }

    get remainingCount() {
        const total = this.warningsByLevel.danger.length + this.warningsByLevel.warning.length;
        return total - this.displayedWarnings.length;
    }
}

export const actionableWarningsField = {
    component: ActionableWarningsField,
};
registry.category("fields").add("actionable_warnings", actionableWarningsField);
