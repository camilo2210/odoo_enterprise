import { registry } from "@web/core/registry";
import { retrieveHMRCClientInfo } from "../../hmrc_api";
import { usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";

export async function HmrcAddClientData(_, action) {
    const orm = usePlugin(ORM);
    const activeId = action.params?.active_id || action.context?.active_id;

    const nextAction = await orm.call(
        'account.return',
        'l10n_uk_process_hmrc_vat_submission',
        [activeId],
        {
            client_data: retrieveHMRCClientInfo(),
        }
    );

    return nextAction;
}

registry.category("actions").add("action_hmrc_add_client_data", HmrcAddClientData)
