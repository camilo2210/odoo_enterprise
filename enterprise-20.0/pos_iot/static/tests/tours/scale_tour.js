/* global posmodel */

import { registry } from "@web/core/registry";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";

class IotHttpServiceDummy {
    action(_iotBoxId, _deviceIdentifier, _payload, onSuccess) {
        onSuccess({
            status: "success",
            result: 2.35,
        });
    }
}

registry.category("web_tour.tours").add("pos_iot_scale_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            {
                content: "mock the connected scale",
                trigger: ".pos .pos-content",
                run: function () {
                    posmodel.scale.iotHttp = new IotHttpServiceDummy();
                    posmodel.scale.connectToScale();
                },
            },
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            Dialog.confirm("Get Weight", ".btn-secondary"),
            {
                content: "gross weight is set",
                trigger: '.gross-weight:contains("2.35")',
            },
            Dialog.confirm("Order"),
            ProductScreen.selectedOrderlineHas("Whiteboard Pen", "2.35", "7.52"),
        ].flat(),
});
