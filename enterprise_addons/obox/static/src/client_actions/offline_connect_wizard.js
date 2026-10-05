import { usePlugin } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { redirect } from "@web/core/utils/urls";

registry.category("actions").add("obox_offline_connected", async (env, action) => {
    const orm = usePlugin(ORM);
    const notification = useService("notification");
    try {
        await browser.fetch(action.params.url);
        redirect(`/odoo/device/${action.params.id}`);
    } catch {
        await orm.unlink("obox.obox", [action.params.id]);
        notification.add(_t("Could not find any Obox with this IP address"), {
            type: "warning",
        });
    }
});
