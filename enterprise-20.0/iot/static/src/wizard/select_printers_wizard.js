import { patch } from "@web/core/utils/patch";
import { SelectPrintersWizard } from "@printer/wizard/select_printers_wizard";

patch(SelectPrintersWizard.prototype, {
    get extractSettings() {
        const { duplex } = this.model.root.evalContextWithVirtualIds;
        return {
            ...super.extractSettings,
            duplex,
        };
    },
});
