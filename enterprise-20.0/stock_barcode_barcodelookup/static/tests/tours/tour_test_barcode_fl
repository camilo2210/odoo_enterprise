/** @odoo-module */

import { registry } from "@web/core/registry";
import { stepUtils } from "@stock_barcode/../tests/tours/tour_step_utils";

registry.category("web_tour.tours").add("test_create_product_from_barcode_lookup", {
    steps: () => [
        {
            content: "check that from the main screen we can create a product from barcode lookup",
            trigger: ".o_stock_barcode_main_menu",
            run: "scan 510002952387",
        },
        {
            trigger: ".o_notification .o_notification_buttons button:contains(New Product)",
            run: "click",
        },
        {
            trigger: ".modal-content",
            run: "press Escape",
        },
        {
            content: "wait for the form to close",
            trigger: "body:not(:has(.modal))",
        },
        {
            content: "close notification",
            trigger: ".o_notification .o_notification_close",
            run: "click",
        },
        {
            content: "check the same in operations tab",
            trigger: ".o_button_operations",
            run: "click",
        },
        {
            content: "wait for the operations page to load",
            trigger: ".o_last_breadcrumb_item:contains('Operations')",
        },
        {
            trigger: "[data-icon='barcode']",
            run: "scan 510002952387",
        },
        {
            trigger: ".o_notification .o_notification_buttons button:contains(New Product)",
            run: "click",
        },
        {
            trigger: ".modal-content",
            run: "press Escape",
        },
        {
            content: "wait for the form to close",
            trigger: "body:not(:has(.modal))",
        },
        {
            content: "close notification",
            trigger: ".o_notification .o_notification_close",
            run: "click",
        },
        {
            content: "check the same in some operation",
            trigger: ".o_kanban_record:first",
            run: "click",
        },
        {
            content: "wait for the specific operation page to load",
            trigger: ".o_last_breadcrumb_item:contains('Test Warehouse')",
        },
        {
            trigger: "[data-icon='barcode']",
            run: "scan 510002952387",
        },
        {
            trigger: ".o_notification .o_notification_buttons button:contains(New Product)",
            run: "click",
        },
        {
            trigger: ".modal-content",
            run: "press Escape",
        },
        {
            content: "wait for the form to close",
            trigger: "body:not(:has(.modal))",
        },
        {
            content: "close notification",
            trigger: ".o_notification .o_notification_close",
            run: "click",
        },
        {
            content: "go back to operations",
            trigger: ".breadcrumb-item:contains('Operations')",
            run: "click",
        },
        {
            content: "go back to main",
            trigger: ".breadcrumb-item:contains('Barcode')",
            run: "click",
        },
        {
            trigger: ".o_stock_barcode_main_menu",
            run: "scan WHIN",
        },
        {
            content: "scan a valid barcode lookup that does not correspond to an existing product.",
            trigger: ".o_barcode_client_action",
            run: "scan 510002952387",
        },
        {
            trigger: ".o_notification .o_notification_buttons button:contains(New Product)",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=name] .o_input",
            run: "edit Lovely Product",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        { trigger: ".o_notification_content:contains(Product created successfully)" },
        ...stepUtils.validateBarcodeOperation(".o_barcode_line"),
    ],
});

registry.category("web_tour.tours").add("test_no_create_product_from_barcode_lookup", {
    steps: () => [
        {
            trigger: ".o_stock_barcode_main_menu",
            run: "scan WHIN",
        },
        {
            trigger: ".o_barcode_client_action",
            run: "scan 510002952387",
        },
        {
            trigger: ".o_notification:not(:has(button:contains(New Product)))",
        },
    ],
});
