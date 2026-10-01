import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect } from "@odoo/hoot";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("getDeliveryProviderName, isFutureOrder, isDirectSale, deliveryOrderType, getOrderStatus, providerOrderId, getOrderData", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    order.delivery_status = "food_ready";
    order.is_instant_order = false;
    expect(order.getDeliveryProviderName()).toEqual("DoorDash");
    expect(order.getOrderStatus()).toEqual("food_ready");
    expect(order.isDirectSale).toEqual(false);
    expect(order.deliveryOrderType).toEqual("partner");
    expect(order.isFutureOrder).toEqual(false);
    expect(order.providerOrderId).toEqual("TST-1756819673");
    const generator = store.ticketPrinter.getGenerator({ models: store.models, order });
    const categories = store.models["pos.category"].map((c) => c.id);
    const changes = generator.generatePreparationData(new Set(categories), {});
    expect(changes[0].extra_data).toEqual({
        company_country_name: "United States",
        company_state_name: "",
        delivery_otp: "123456",
        delivery_provider_name: "DoorDash",
        employee_name: "Administrator",
        general_customer_note: false,
        internal_note: false,
        order_label: false,
        prefix: "Order",
        prepTicketBarcode: false,
        preset_time: false,
        reprint: false,
        time: "10:30",
        vat_label: "TIN",
        is_instant_order: false,
    });
});

test("deliveryOtp returns order OTP", async () => {
    const store = await setupPosEnvForPrepDisplay();

    const orderWithOtp = await getUrbanPiperFilledOrder(store);
    expect(orderWithOtp.deliveryOtp).toBe("123456");

    const orderWithoutOtp = store.addNewOrder();
    orderWithoutOtp.delivery_json = "{}";
    expect(orderWithoutOtp.deliveryOtp).toBeEmpty();
});

test("isFutureOrder", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    order.preset_time = "2025-03-01 06:02:25";
    expect(order.deliveryTime).toEqual("01/03/2025 06:02:25");
    expect(order.isFutureOrder).toEqual(true);
});

test("deliveryCustomerData", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const deliveryCustomerData = order.deliveryCustomerData;

    expect(deliveryCustomerData.name).toBe("Monkey D. Luffy");
    expect(deliveryCustomerData.phone).toBe("+91 99999 11111");
    expect(deliveryCustomerData.email).toBe("future.king@onepiece.com");
    expect(deliveryCustomerData.address).toBe(
        "Thousand sunny, Near Grand Line, East Blue, Windmill Village, 000001"
    );
});
