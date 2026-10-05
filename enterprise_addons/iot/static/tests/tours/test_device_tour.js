import * as IotUtils from "@iot/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("iot_device_test_printer", {
    steps: () =>
        [
            IotUtils.mockIotActionRequest(),
            IotUtils.openTestShopIotBox(),
            {
                content: "click on device 'Receipt Printer'",
                trigger: ".o_data_cell:contains('printer_identifier')",
                run: "click",
            },
            {
                content:
                    "Ensure the record is loaded (avoid clicking on 'Test' on the IoT Box record)",
                trigger: ".o_last_breadcrumb_item:contains('Receipt Printer')",
                run: "click",
            },
            {
                content: "Click button 'Test'",
                trigger: ".o_statusbar_buttons button:contains('Test')",
                run: "click",
            },
            {
                content: "Check if notification is displayed",
                trigger: ".o_notification:contains('Test page printed')",
                run: "click",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("iot_device_test_fdm", {
    steps: () =>
        [
            IotUtils.mockIotActionRequest(),
            IotUtils.openTestShopIotBox(),
            {
                content: "click on device 'FDM'",
                trigger: ".o_data_cell:contains('mock_fdm')",
                run: "click",
            },
            {
                content:
                    "Ensure the record is loaded (avoid clicking on 'Test' on the IoT Box record)",
                trigger: ".o_last_breadcrumb_item:contains('FDM')",
                run: "click",
            },
            {
                content: "Click button 'Test'",
                trigger: ".o_statusbar_buttons button:contains('Test')",
                run: "click",
            },
            {
                content: "Check if notification is displayed",
                trigger:
                    ".o_notification:contains('Fiscal Data Module is connected and operational')",
                run: "click",
            },
        ].flat(),
});
