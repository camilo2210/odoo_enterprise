import * as IotUtils from "@iot/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("iot_test_update_display_url", {
    steps: () =>
        [
            IotUtils.mockIotActionRequest(),
            IotUtils.openTestShopIotBox(),
            {
                content: "click on device 'Display'",
                trigger: ".o_data_cell:contains('mock_display')",
                run: "click",
            },
            {
                content: "Fill field 'Display URL'",
                trigger: "div[name='display_url'] input",
                run: "fill https://www.odoo.com",
            },
            {
                content: "Save the device form",
                trigger: ".o_form_button_save",
                run: "click",
            },
            IotUtils.waitForIotRequest(2000),
        ].flat(),
});
