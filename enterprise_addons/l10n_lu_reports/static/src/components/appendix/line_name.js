import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportLineName } from "@account_reports/components/account_report/line_name/line_name";
import { usePlugin } from "@odoo/owl";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";

export class L10nLUAppendixLineName extends AccountReportLineName {
    static template = "l10n_lu_reports.AppendixLineName";

    dialog = usePlugin(DialogPlugin);

    async recomputeAction(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.dialog.add(ConfirmationDialog, {
            body: _t("You are about to delete all this year's appendix lines and calculate new ones. This action is irreversible."),
            confirmLabel: _t("Proceed"),
            confirm: async () => {
                await this.controller.reportAction(ev, 'action_open_appendix_view', {'recompute': true});
            },
            cancel: () => { },
        });
    }
}

AccountReportController.registerCustomComponent(L10nLUAppendixLineName);
