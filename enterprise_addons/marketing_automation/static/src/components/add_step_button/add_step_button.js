import { _t } from "@web/core/l10n/translation";
import { Component, useProps, types as t, usePlugin } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";

export class AddStepButton extends Component {
    static template = "marketing_automation.AddStepButton";
    static components = { Dropdown, DropdownItem };

    props = useProps({
        style: t.string().optional(),
        icon: t.string().optional(),
        title: t.string().optional(),
        onSelectedStep: t.function(),
        slots: t.object().optional(),
        disabledStepTypes: t.array().optional(),
    });

    setup() {
        this.notification = usePlugin(NotificationPlugin);
    }

    /**
     * @param {string} stepType
     * @returns {Function}
     */
    getDropdownItemProps(stepType) {
        if ((this.props.disabledStepTypes || []).includes(stepType)) {
            return {
                closingMode: "none",
                onSelected: () => {
                    this.notification.add(_t("You cannot add this step here!"), {
                        type: "danger",
                    });
                },
            };
        }
        return {
            onSelected: () => this.props.onSelectedStep(stepType),
        };
    }
}
