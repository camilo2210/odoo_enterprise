import { Component, t, useProps } from "@odoo/owl";

export class AccountReportEllipsisPopover extends Component {
    static template = "account_reports.AccountReportEllipsisPopover";
    props = useProps({
        close: t.function(),
        name: t.string(),
        copyEllipsisText: t.function(),
    });
}
