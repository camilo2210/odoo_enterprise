import { Message } from "@mail/core/common/message";
import { AccountReportController } from "@account_reports/components/account_report/controller";

import { t, useProps } from "@odoo/owl";

export class AccountReportMessage extends Message {
    setup() {
        super.setup(...arguments);
        this.accountReportProps = useProps({
            reportController: t.instanceOf(AccountReportController).optional(),
        });
    }
}
