import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { AccountReportComposer } from "./composer";
import { AccountReportThread } from "./thread";
import { AccountReportController } from "@account_reports/components/account_report/controller";

import { t, useProps } from "@odoo/owl";

export class AccountReportChatter extends Chatter {
    static template = "account_reports.Chatter";
    static components = {
        ...Chatter.components,
        Composer: AccountReportComposer,
        Thread: AccountReportThread,
    };

    setup() {
        super.setup(...arguments);
        this.accountReportProps = useProps({
            date_to: t.string(),
            list: t.any().optional(),
            reportController: t.instanceOf(AccountReportController).optional(),
        });
    }
}
