import { signal, useEffect, usePlugin } from "@odoo/owl";
import { UIPlugin } from "@web/core/ui/ui_plugin";

import { ListRenderer } from "@web/views/list/list_renderer";
import { AccountReportChatter } from "@account_reports/components/mail/chatter";
import { auditBalanceListChatterPlugin } from "./account_audit_balance_list_chatter_plugin";

export class AccountAuditBalanceListRenderer extends ListRenderer {
    static template = "account_reports.account_audit_balance_list_renderer";

    static components = {
        ...ListRenderer.components,
        AccountReportChatter,
    };

    AuditChatterRef = signal.ref();

    ui = usePlugin(UIPlugin);
    chatterPlugin = usePlugin(auditBalanceListChatterPlugin);

    setup() {
        super.setup();
        useEffect(() => {
            if (this.props.list.editedRecord) {
                this.chatterPlugin.openChatter(this.props.list.editedRecord.evalContext.id);
            } else {
                this.chatterPlugin.closeChatter();
            }
        });
    }

    onGlobalClick(event) {
        if (this.AuditChatterRef().contains(event.target)) {
            // ignore clicks inside the chatter as we dont want it to close when clicking inside it
            return;
        }
        super.onGlobalClick(event);
    }

    getCellClass(column, record) {
        const classNames = super.getCellClass(column, record);
        if (column.name === 'audit_balance' && record.data.audit_balance_show_warning
            || column.name === 'audit_previous_balance' && record.data.audit_previous_balance_show_warning) {
            return `${classNames} table-warning`;
        }
        return classNames;
    }
}
