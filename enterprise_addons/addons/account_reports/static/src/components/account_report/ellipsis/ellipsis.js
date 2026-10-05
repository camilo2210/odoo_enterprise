import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";

import { registry } from "@web/core/registry";
import { PopoverPlugin } from "@web/core/popover/popover_plugin";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";

import { Component, t, usePlugin, useProps } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportEllipsisPopover } from "@account_reports/components/account_report/ellipsis/popover/ellipsis_popover";


export class AccountReportEllipsis extends Component {
    static template = "account_reports.AccountReportEllipsis";
    props = useProps({
        name: t.signal(t.string()).optional(),
        no_format: t.signal(t.string()).optional(),
        type: t.or([t.signal(t.string()), t.function([],t.string())]).optional(),
        maxCharacters: t.number(),
    });

    controller = usePlugin(AccountReportController);
    popover = usePlugin(PopoverPlugin);
    notification = usePlugin(NotificationPlugin);

    //------------------------------------------------------------------------------------------------------------------
    // Ellipsis
    //------------------------------------------------------------------------------------------------------------------
    get triggersEllipsis() {
        const name = this.props.name?.();
        return name && name.length > this.props.maxCharacters;
    }

    copyEllipsisText() {
        navigator.clipboard.writeText(this.props.name?.());
        this.notification.add(_t("Text copied"), { type: 'success' });
        this.popoverCloseFn();
        this.popoverCloseFn = null;
    }

    showEllipsisPopover(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        if (this.popoverCloseFn) {
            this.popoverCloseFn();
            this.popoverCloseFn = null;
        }

        this.popoverCloseFn = this.popover.add(
            ev.currentTarget,
            AccountReportEllipsisPopover,
            {
                name: this.props.name?.(),
                copyEllipsisText: this.copyEllipsisText.bind(this),
            },
            {
                closeOnClickAway: true,
                position: localization.direction === "rtl" ? "left" : "right",
            },
        );
    }
}

registry.category("account_reports.default_components").add("AccountReportEllipsis", AccountReportEllipsis);
