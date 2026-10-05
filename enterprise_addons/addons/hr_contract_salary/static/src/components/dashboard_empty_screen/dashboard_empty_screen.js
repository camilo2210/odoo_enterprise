import { patch } from "@web/core/utils/patch";
import { DashboardEmptyScreen } from "@hr_payroll/components/dashboard/dashboard_empty_screen/dashboard_empty_screen";

patch(DashboardEmptyScreen.prototype, {
    viewSalarySimulator() {
        this.action.doAction("hr_contract_salary.action_hr_salary_simulator");
    },
});
