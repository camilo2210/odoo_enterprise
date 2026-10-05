import { Plugin } from "@odoo/owl";
import { services } from "@web/core/services";

export class AccountDuplicateTransactionsPlugin extends Plugin {
    selectedLines = new Set();

    updateLine(selected, id) {
        this.selectedLines[selected ? "add" : "delete"](id);
    }
}

services.add(AccountDuplicateTransactionsPlugin);
