import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { definePosSelfModels } from "@pos_self_order/../tests/unit/data/generate_model_definitions";
import { setupSelfPosEnv, getFilledSelfOrder } from "@pos_self_order/../tests/unit/utils";
import { onRpc, patchWithCleanup, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { PosConfig } from "@point_of_sale/../tests/unit/data/pos_config.data";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";

definePosSelfModels();

beforeEach(async () => {
    onRpc("/iot_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    // Fonts
    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/point_of_sale/static/*", () => "");
    onRpc("/web/static/*", () => "");
});

const setupConfirmationPage = async (mode, service_mode, pay_after) => {
    const store = await setupSelfPosEnv(mode, service_mode, pay_after);
    patchWithCleanup(store.ticketPrinter, {
        async generateIframe() {},
        async generateImage() {
            return document.createElement("canvas");
        },
        async setIframeSizeFromPrinter() {},
    });
    const order = await getFilledSelfOrder(store);
    return await mountWithCleanup(ConfirmationPage, {
        props: {
            screenMode: "order",
            orderAccessToken: order.access_token,
        },
    });
};

describe("mobile Self Ordering", () => {
    test("Local network is disabled on setup", async () => {
        let localNetworkCalled = false;
        onRpc("/iot_drivers/action", () => {
            localNetworkCalled = true;
            return true;
        });

        // need to patch as `self_order_service.setup` is run before `setupSelfPosEnv`
        // sets mode to "mobile"
        patchWithCleanup(PosConfig._records[0], { self_ordering_mode: "mobile" });
        const confirmationPage = await setupConfirmationPage("mobile");
        await confirmationPage.printOrderChanges();

        expect(localNetworkCalled).toBe(false);
    });

    test("shouldUpdateLastOrderChange returns false with IoT prep printer", async () => {
        const store = await setupSelfPosEnv("mobile");

        expect(store.shouldUpdateLastOrderChange()).toBe(false);
    });

    test("shouldUpdateLastOrderChange returns true with non-IoT prep printer", async () => {
        patchWithCleanup(PosConfig._records[0], { preparation_printer_ids: [] });
        const store = await setupSelfPosEnv("mobile");

        expect(store.shouldUpdateLastOrderChange()).toBe(true);
    });
});

describe("kiosk Self Ordering", () => {
    test("Local network is NOT disabled on setup", async () => {
        let localNetworkCalled = false;
        onRpc("/iot_drivers/action", () => {
            localNetworkCalled = true;
        });

        const confirmationPage = await setupConfirmationPage("kiosk", "counter", "meal");
        await confirmationPage.printOrderChanges();

        expect(localNetworkCalled).toBe(true);
    });
});
