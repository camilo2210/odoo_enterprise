import { SalaryPackage } from "@hr_contract_salary/interactions/hr_contract_salary";
import { patch } from "@web/core/utils/patch";

patch(SalaryPackage.prototype, {
    updateGrossToNetModal(data) {
        super.updateGrossToNetModal(data);
        const submitButton = this.el.querySelector("button#hr_cs_submit");
        if (submitButton) {
            submitButton.disabled = !!data.configurator_warning;
        }
    },
});
