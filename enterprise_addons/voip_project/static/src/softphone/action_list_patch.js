import { ActionList } from "@voip/softphone/action_list";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(ActionList.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },
    getCreateActions() {
        return [...super.getCreateActions(), this.getCreateTaskAction()];
    },
    getViewActions() {
        return [...super.getViewActions(), this.getViewTasksAction()];
    },
    /**
     * Get the view tasks action.
     * @returns {Object} Action object
     */
    getViewTasksAction() {
        return {
            name: this.contact?.commercial_partner_task_count > 1 ? _t("Tasks") : _t("Task"),
            title:
                this.contact?.commercial_partner_task_count > 1
                    ? _t("View tasks")
                    : _t("View task"),
            icon: "check",
            predicate: () => this.contact?.commercial_partner_task_count,
            onClick: async () => {
                const action = await this.orm.call("res.partner", "action_voip_view_tasks", [
                    this.contact.id,
                ]);
                action.target = this.ui.isSmall ? "new" : "current";
                this.action.doAction(action);
            },
        };
    },
    getCreateTaskAction() {
        return {
            name: _t("Task"),
            title: _t("Create a task"),
            icon: "check",
            predicate: () => this.voip.softphone.shouldShowTaskButton,
            onClick: () => {
                this.action.doAction({
                    type: "ir.actions.act_window",
                    name: _t("Create a task"),
                    res_model: "project.task",
                    views: [[false, "form"]],
                    context: {
                        default_partner_id: this.contact?.id,
                    },
                    target: this.ui.isSmall ? "new" : "current",
                });
            },
        };
    },
});
