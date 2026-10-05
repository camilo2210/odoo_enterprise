import { usePlugin } from "@odoo/owl";
import { download } from "@web/core/network/download";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { UIPlugin } from "@web/core/ui/ui_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

async function executeAccountReportDownload({ action }) {
    const ui = usePlugin(UIPlugin);
    const actionPlugin = usePlugin(ActionPlugin);
    const orm = usePlugin(ORM);
    ui.block();

    const url = "/account_reports";
    const data = action.data;

    try {
        await download({ url, data });
        if (!data.no_closing_after_download)
            if (data.next_action) {
                actionPlugin.doAction(data.next_action);
            } else {
                actionPlugin.doAction({type: 'ir.actions.act_window_close'});
            }
    } catch (e) {
        if (e.exceptionName === 'AccountReportFileDownloadException') {
            const reportOptions = JSON.parse(data.options);
            const reportAction = await orm.call(
                'account.report',
                'open_account_report_file_download_error_wizard',
                [reportOptions.report_id, e.data.arguments[0], e.data.arguments[1]],
            );
            actionPlugin.doAction(reportAction);
        } else {
            throw e;
        }
    } finally {
        ui.unblock();
    }
}

registry
    .category("action_handlers")
    .add('ir_actions_account_report_download', executeAccountReportDownload);
