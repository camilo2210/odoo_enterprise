import { usePlugin } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { redirect } from "@web/core/utils/urls";

const ODOO_PROXY_DISCOVER_BOXES_ENDPOINT =
    "https://iot-proxy.odoo.com/odoo-enterprise/iot/discover-boxes";

export async function discoverObox() {
    const orm = usePlugin(ORM);
    const notification = useService("notification");
    const action = useService("action");

    try {
        const response = await rpc(ODOO_PROXY_DISCOVER_BOXES_ENDPOINT);
        const discoveredOboxes = response.filter(
            (box) => typeof box.serial_number === "string" && box.serial_number?.startsWith("ODO")
        );
        if (discoveredOboxes.length === 0) {
            action.doAction("obox.action_obox_offline_connect_offline");
            return;
        }

        const newOboxId = await orm.call("obox.obox", "pair_obox", [
            discoveredOboxes[0].pairing_code,
        ]);
        if (newOboxId) {
            redirect(`/odoo/device/${newOboxId}`);
        } else {
            notification.add(_t("Failed to pair Obox %s", discoveredOboxes[0].serial_number));
        }
    } catch (error) {
        console.error(error);
        notification.add(_t("Failed to discover Oboxes on local network"), { type: "danger" });
    }
}

registry.category("actions").add("discover_obox", discoverObox);
