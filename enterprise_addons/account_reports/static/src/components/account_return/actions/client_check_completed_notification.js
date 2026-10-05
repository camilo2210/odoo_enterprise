import { usePlugin } from "@odoo/owl";
import { GlobalBusPlugin } from "@web/core/global_bus_plugin";
import { registry } from "@web/core/registry";


export async function AccountReturnRefreshHandler(_, action) {
    const params = action.params || {};
    const bus = usePlugin(GlobalBusPlugin).bus;
    bus.trigger("return_reload_model", {resIds: params.return_ids});
    return params.next_action;
}

registry.category("actions").add("action_return_refresh", AccountReturnRefreshHandler)
