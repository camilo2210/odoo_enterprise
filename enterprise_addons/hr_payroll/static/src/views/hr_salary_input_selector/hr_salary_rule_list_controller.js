import { proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

export class SalaryRuleListController extends ListController {

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = proxy({
            disabled: false,
        });
    }

    async onReload() {
        return this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
    }

    async onClose() {
        return this.actionService.doAction({type: "ir.actions.act_window_close"});
    }
}
export const salaryRuleListController = {
    ...listView,
    Controller: SalaryRuleListController,
    buttonTemplate: "hr_payroll.SalaryRuleListController.Buttons",
};

registry.category("views").add("hr_salary_rule_list", salaryRuleListController);