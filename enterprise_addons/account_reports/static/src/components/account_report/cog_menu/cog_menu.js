import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

import { Component, usePlugin } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";


export class AccountReportCogMenu extends Component {
    static template = "account_reports.AccountReportCogMenu";
    static components = {Dropdown, DropdownItem};

    controller = usePlugin(AccountReportController);

    //------------------------------------------------------------------------------------------------------------------
    // Buttons
    //------------------------------------------------------------------------------------------------------------------
    get cogButtons() {
        const buttons = [];

        for (const button of this.controller.buttons) {
            if (!button.always_show) {
                buttons.push({
                    ...button,
                    onClick: (ev) => this.controller.buttonAction(ev, button),
                });
            }
        }

        return buttons;
    }
}
