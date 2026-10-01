import { getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { serverState } from "@web/../tests/web_test_helpers";

export const getUrbanPiperFilledOrder = async (store) => {
    const order = await getFilledOrder(store);
    order.source = "online";
    order.delivery_provider_id = store.models["pos.delivery.provider"].get(1);
    order.prep_time = 25.0;
    order.setPartner(store.models["res.partner"].get(serverState.partnerId));
    order.delivery_identifier = "OID001";
    order.preset_id = false;
    order.delivery_json = JSON.stringify({
        order: {
            details: {
                created: 1735879045123,
                delivery_datetime: 1735880545123,
                ext_platforms: [
                    {
                        id: "TST-1756819673",
                        delivery_type: "partner",
                        name: "DoorDash",
                        extras: { order_otp: "123456" },
                    },
                ],
            },
            store: { name: "Main Branch" },
            payment: [{ option: "card" }],
        },
        customer: {
            name: "Monkey D. Luffy",
            phone: "+91 99999 11111",
            email: "future.king@onepiece.com",
            address: {
                line_1: "Thousand sunny",
                line_2: "Near Grand Line, East Blue",
                city: "Windmill Village",
                pin: "000001",
            },
        },
    });
    return order;
};
