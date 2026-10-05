import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class CreateJournalButton extends Component {
    static template = "account.CreateJournalButton";
    static components = { DropdownItem };

    setup() {
        this.action = useService("action");
    }

    openWizard() {
        this.action.doAction("account_accountant.action_journal_create_wizard");
    }
}

export const CreateJournalButtonActionMenu = {
    Component: CreateJournalButton,
    isDisplayed: ({ config, searchModel}) =>
        searchModel.resModel === "account.journal" &&
        config.viewSubType === 'account_dashboard_kanban',
};

registry.category("cogMenu").add("account-create-journal", CreateJournalButtonActionMenu);
