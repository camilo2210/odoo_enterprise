import { getFilledOrder } from "@point_of_sale/../tests/unit/utils";

export const getPlatformFilledOrder = async (store) => {
    const order = await getFilledOrder(store);

    order.platform_order_provider_id = store.models["platform.order.provider"].get(1);
    order.source = "platform_order";
    order.preset_id = false;
    return order;
};
