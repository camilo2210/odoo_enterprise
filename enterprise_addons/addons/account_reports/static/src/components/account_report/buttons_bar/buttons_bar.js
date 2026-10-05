import { Component, usePlugin } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";


export class AccountReportButtonsBar extends Component {
    static template = "account_reports.AccountReportButtonsBar";

    controller = usePlugin(AccountReportController);

    //------------------------------------------------------------------------------------------------------------------
    // Buttons
    //------------------------------------------------------------------------------------------------------------------
    get barButtons() {
        const buttons = [];

        for (const button of this.controller.buttons) {
            if (button.always_show) {
                buttons.push(button);
            }
        }

        return buttons;
    }
}
