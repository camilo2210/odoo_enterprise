import { usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

export async function AccountReturnCloseWizard(_, action) {
    const params = action.params || {};
    usePlugin(ActionPlugin).doAction({
        type: 'ir.actions.act_window_close'
    });
    return params.next_action;
}

registry.category("actions").add("action_return_close_wizard", AccountReturnCloseWizard);
