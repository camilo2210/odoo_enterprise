import { Component, t, useProps } from "@odoo/owl";

export class AccountReportDebugPopover extends Component {
    static template = "account_reports.AccountReportDebugPopover";
    props = useProps({
        close: t.function(),
        expressionsDetail: t.array(),
        onClose: t.function(),
    });
}
