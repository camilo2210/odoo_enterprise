import { Thread } from "@mail/core/common/thread";
import { AccountReportMessage } from "./message";
import { AccountReportController } from "@account_reports/components/account_report/controller";

import { t, useProps } from "@odoo/owl";

export class AccountReportThread extends Thread {
    static template = "account_reports.Thread";
    static components = { ...Thread.components, Message: AccountReportMessage };

    setup() {
        super.setup(...arguments);
        this.accountReportProps = useProps({
            reportController: t.instanceOf(AccountReportController).optional(),
        });
    }
}
