import { Plugin } from "@odoo/owl";

export class AccrualPlugin extends Plugin {
    entryDate = undefined;

    exportState() {
        return {
            accrualEntryDate: this.entryDate,
        };
    }

    importState(state) {
        this.entryDate = state.accrualEntryDate;
    }

    toContext() {
        return {
            accrual_entry_date: this.entryDate,
        };
    }
}
