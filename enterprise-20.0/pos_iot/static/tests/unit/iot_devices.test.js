import { beforeEach, expect, test } from "@odoo/hoot";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { mockService, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { IoTPrinter } from "@pos_iot/app/utils/printer/iot_printer";

definePosModels();

beforeEach(async () => {
    onRpc("/iot_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    // Fonts
    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/point_of_sale/static/*", () => "");
    onRpc("/web/static/*", () => "");

    mockService("iot_http", {
        action: async () => {},
        onMessage: async () => {},
    });
});

test("IoT Devices are loaded", async () => {
    const store = await setupPosEnv();
    store.ticketPrinter.selectPrinter();
    expect(store.config.use_iot_box).toBe(true);
    expect(store.iotHttp.status).toBe("longpolling");

    // Drivers are set properly
    expect(store.scale._scaleDevice).not.toBeEmpty();

    // kitchen printers
    expect(store.config.preparation_printer_ids).toHaveLength(1); // createPrinter() works properly
    // receipt printer
    expect(store.ticketPrinter.defaultPrinter._instance).toBeInstanceOf(IoTPrinter); // printer should be connected
    expect(store.ticketPrinter.defaultPrinter.iot_device_id.iot_id.id).toBe(2);
    expect(store.ticketPrinter.defaultPrinter.iot_device_id.identifier).toBe("printer_identifier");
});
