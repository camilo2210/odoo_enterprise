import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { ORM } from "@web/core/orm_plugin";
import { usePlugin } from "@odoo/owl";

const IOT_PROXY_DISCOVER_BOXES_ENDPOINT =
    "https://iot-proxy.odoo.com/odoo-enterprise/iot/discover-boxes";

export async function discoverIotBoxes() {
    const orm = usePlugin(ORM);
    const discoveredBoxes = [];

    try {
        const response = await rpc(IOT_PROXY_DISCOVER_BOXES_ENDPOINT);
        const iotBoxes = response.filter((box) => !box.serial_number?.startsWith("ODO"));
        discoveredBoxes.push(...iotBoxes);
    } catch (error) {
        console.debug("Failed to retrieve local IoT boxes: " + error);
    }

    return orm.call("iot.box", "connect_iot_box", [discoveredBoxes]);
}

registry.category("actions").add("discover_iot_boxes", discoverIotBoxes);
