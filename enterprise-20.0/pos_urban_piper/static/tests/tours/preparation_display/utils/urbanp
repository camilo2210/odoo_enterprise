export function checkDeliveryState(state) {
    return {
        content: `Check that the delivery state "${state}" is displayed on the order card`,
        trigger: `.o_pdis_order_card_header_top_delivery div:contains("${state}")`,
    };
}

export function clickDeliveryOrder(orderOtp) {
    return {
        content: `Click on the delivery order card with OTP "${orderOtp}"`,
        trigger: `.o_pdis_order_card_header_top_delivery:contains("${orderOtp}")`,
        run: "click",
    };
}

export function clickDoneOnDeliveryOrder(orderOtp) {
    return {
        content: `Mark the delivery order with OTP "${orderOtp}" as done`,
        trigger: `.o_pdis_order_card:has(.o_pdis_order_card_header_top_delivery:contains("${orderOtp}")) .o_pdis_order_card_footer button:contains("Done")`,
        run: "click",
    };
}

export function isFutureDeliveryOrder(orderOtp) {
    return {
        content: `Check that the delivery order with OTP "${orderOtp}" is scheduled for a future time`,
        trigger: `.o_pdis_order_card_header:has(.o_pdis_order_card_header_top_delivery:contains("${orderOtp}")):has(.text-info:contains("Scheduled At:"))`,
    };
}
