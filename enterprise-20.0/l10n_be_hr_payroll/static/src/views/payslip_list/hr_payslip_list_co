import { patch } from "@web/core/utils/patch";
import { PayslipListController } from "@hr_payroll/views/payslip_list/hr_payslip_list_controller";

patch(PayslipListController.prototype, {
    getSelectionFields() {
        return [...super.getSelectionFields(), "l10n_be_needs_flxwage_declaration"];
    },

    displayButton(button) {
        if (button.clickParams.name === "action_create_flxwage_declaration") {
            return (this.state.selectionStates || []).some(
                (p) =>
                    p.l10n_be_needs_flxwage_declaration &&
                    ["validated", "paid"].includes(p.state)
            );
        }
        return super.displayButton(button);
    },
});
