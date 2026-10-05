import { ActionList } from "@voip/softphone/action_list";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(ActionList.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },
    getViewActions() {
        return [...super.getViewActions(), this.getViewEmployeeAction()];
    },
    /**
     * Get the view employee action.
     * @returns {Object} Action object
     */
    getViewEmployeeAction() {
        return {
            name: this.contact?.employees_count > 1 ? _t("Employees") : _t("Employee"),
            title: this.contact?.employees_count > 1 ? _t("View employees") : _t("View employee"),
            icon: "badge",
            predicate: () => this.contact?.employees_count,
            onClick: async () => {
                const action = await this.orm.call("res.partner", "action_open_employees", [
                    this.contact.id,
                ]);
                action.target = this.ui.isSmall ? "new" : "current";
                this.action.doAction(action);
            },
        };
    },
});
