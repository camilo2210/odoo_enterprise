/* global posmodel */

import { registry } from "@web/core/registry";
import * as Utils from "@pos_self_order/../tests/tours/utils/common";
import * as IotUtils from "@iot/../tests/tours/utils/common";
import * as CartPage from "@pos_self_order/../tests/tours/utils/cart_page_util";
import * as ProductPage from "@pos_self_order/../tests/tours/utils/product_page_util";

registry.category("web_tour.tours").add("self_order_kiosk_iot_printer", {
    steps: () => [
        IotUtils.mockIotActionRequest(),
        Utils.checkIsNoBtn("My Order"),
        Utils.clickBtn("Order Now"),
        ProductPage.clickCategory("Miscellaneous"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        CartPage.checkProduct("Coca-Cola", "2.53", "1"),
        Utils.clickBtn("Order"),
        IotUtils.waitForIotRequest(6000), // wait for timeout
        Utils.clickBtn("Close"),
    ],
});

class IotHttpServiceDummy {
    cid = "";
    action(_iotBoxId, _deviceIdentifier, params, onSuccess) {
        this.cid = params.cid;
        setTimeout(
            () =>
                onSuccess({
                    status: "success",
                    result: {
                        Response: "WaitingForCard",
                        cid: this.cid,
                    },
                }),
            1000
        );
    }
    onMessage(_iotBoxId, _deviceIdentifier, onSuccess) {
        setTimeout(
            () =>
                onSuccess({
                    status: "success",
                    result: {
                        Response: "Approved",
                        Ticket: "Sample Ticket Content",
                        Card: "**** **** **** 4242",
                        PaymentTransactionID: "1234567890",
                        cid: this.cid,
                    },
                }),
            1000
        );
        return Promise.resolve();
    }
}

registry.category("web_tour.tours").add("self_order_kiosk_iot_worldline", {
    steps: () => [
        Utils.checkIsNoBtn("My Order"),
        {
            content: "mock iotHttpService",
            trigger: ".btn:contains('Order Now')",
            run: function () {
                posmodel.iotHttp = new IotHttpServiceDummy();
            },
        },
        Utils.clickBtn("Order Now"),
        ProductPage.clickCategory("Miscellaneous"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        CartPage.checkProduct("Coca-Cola", "2.53", "1"),
        Utils.clickBtn("Pay"),
        IotUtils.waitForIotRequest(6000), // wait for timeout
        Utils.clickBtn("Close"),
        Utils.checkBtn("Order Now"),
    ],
});
