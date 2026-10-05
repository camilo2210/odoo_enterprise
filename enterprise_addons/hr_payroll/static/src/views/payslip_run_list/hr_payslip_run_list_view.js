import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { PayRunListController } from "./hr_payslip_run_list_controller";

const PayRunListView = {
    ...listView,
    Controller: PayRunListController,
    // custom New button so onClickCreate is bypassed in all display modes
    buttonTemplate: "hr_payroll.PayRunListView.Buttons",
};

registry.category("views").add("payslip_run_list", PayRunListView);
