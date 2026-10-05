import { SelectMenu } from "@web/core/select_menu/select_menu";

export class HrContractSalarySelectMenu extends SelectMenu {
    static template = "hrContractSalary.SelectMenu";

    onStateChanged(open){
        super.onStateChanged(open);
        if (open) {
            this.inputRefs.menu()?.focus();
        }
    }

    getItemClass(choice) {
        if (this.isOptionSelected(choice)) {
            return "o_select_menu_item fw-bolder bg-primary text-white";
        } else {
            return "o_select_menu_item";
        }
    }
}
