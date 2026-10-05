import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { location } from "@web/core/browser/browser";
import { retrieveHMRCClientInfo } from "../../hmrc_api";
import { usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

export async function HmrcRedirectAction() {
    const actionPlugin = usePlugin(ActionPlugin);
    const dialog = usePlugin(DialogPlugin);
    const orm = usePlugin(ORM);
    const params = new URLSearchParams(location.search);

    const returnIdParam = params.get("return_id");
    if (!returnIdParam) {
        dialog.add(ConfirmationDialog, {
            title: _t("Invalid Operation"),
            body: _t("Missing return_id parameter in the URL."),
        });
        return;
    }
    const returnId = Number(returnIdParam);

    const returnAction = await orm.call(
        "account.return",
        "action_open_account_return",
        [returnId]
    );

    const sendHMRCWizardAction = await orm.call(
        "account.return",
        "action_open_send_to_hmrc_wizard",
        [returnId],
        {
            client_data: retrieveHMRCClientInfo(),
        }
    );

    // 1: open the related account return's check view
    await actionPlugin.doAction(returnAction);

    // 2: then open the Send to HMRC wizard
    actionPlugin.doAction(sendHMRCWizardAction);

    return;
}

registry.category("actions").add("l10n_uk_hmrc_redirect", HmrcRedirectAction);
