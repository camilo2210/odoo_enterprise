import { proxy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class ChallanPayslipListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = proxy({
            disabled: false,
        });
    }

    get challanId() {
        return this.props.context.challan_id;
    }

    async onAddToChallan() {
        this.state.disabled = true;
        const payslipIds = await this.model.root.getResIds(true);
        await this.orm.call("l10n.in.tds.challan", "action_import_payslips", [
            [this.challanId],
            payslipIds,
        ]);
        return this.actionService.doAction({
            type: "ir.actions.client",
            tag: "display_notification",
            params: {
                type: "warning",
                message: _t("Only the payslips with TDS deduction are imported."),
                next: { type: "ir.actions.act_window_close" },
            },
        });
    }

    async onDiscard() {
        return this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }
}

export const challanPayslipListView = {
    ...listView,
    Controller: ChallanPayslipListController,
    buttonTemplate: "l10n_in_hr_payroll.ChallanPayslipListController.Buttons",
};

registry.category("views").add("l10n_in_challan_payslip_list", challanPayslipListView);
