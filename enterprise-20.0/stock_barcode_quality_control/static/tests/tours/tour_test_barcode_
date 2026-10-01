import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_operation_quality_check_barcode", {
    steps: () => [
        {
            trigger: ".o_button_operations",
            run: "click",
        },
        {
            trigger: ".o_barcode_picking_type:contains(Receipts)",
            run: "click",
        },
        {
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product1",
        },
        {
            trigger: "[data-icon='edit']",
            run: "click",
        },
        {
            trigger: ".o_digipad_increment",
            run: "click",
        },
        {
            trigger: ".o_save",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product2",
        },
        {
            trigger:
                ".o_barcode_line:has(.o_barcode_line_title:contains(product2)) button.o_add_quantity",
            run: "click",
        },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 1)) button[name=do_pass]",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 2)) button[name=do_fail]",
            run: "click",
        },
        {
            trigger: ".o_web_client:not(.modal-open) .o_validate_page",
            run: "click",
        },
        {
            trigger: ".o_notification_bar.bg-success",
        },
        /* Now test Quality check button appears on footer after clicking X on QC */
        {
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product3",
        },
        { trigger: ".o_barcode_line" },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            content: "Close the QC wizard without passing or failing",
            trigger: ".modal-content button.btn-close",
            run: "click",
        },
        {
            content: "Check QC button is on footer",
            trigger: "button.o_check_quality",
        },
    ],
});

registry.category("web_tour.tours").add("test_operation_quality_check_delivery_barcode", {
    steps: () => [
        {
            trigger: ".o_button_operations",
            run: "click",
        },
        {
            trigger: ".o_kanban_record:contains('Delivery')",
            run: "click",
        },
        {
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product1",
        },
        {
            trigger: "[data-icon='edit']",
            run: "click",
        },
        {
            trigger: ".o_digipad_increment",
            run: "click",
        },
        {
            trigger: ".o_save",
            run: "click",
        },
        {
            trigger: ".o_barcode_lines",
        },
        {
            trigger: ".o_barcode_lines",
            run: "scan product2",
        },
        {
            trigger:
                ".o_barcode_line:has(.o_barcode_line_title:contains(product2)) button.o_add_quantity",
            run: "click",
        },
        {
            trigger: ".o_validate_page.btn-secondary",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 1)) button[name=do_pass]",
            run: "click",
        },
        {
            trigger: ".modal-content:has(.modal-header:contains(product 2)) button[name=do_fail]",
            run: "click",
        },
        {
            trigger: ".o_validate_page.btn-primary",
            run: "click",
        },
        {
            trigger: ".o_notification_bar.bg-success",
        },
    ],
});

registry.category("web_tour.tours").add("test_quality_check_partial_reception_barcode", {
    steps: () => [
        {
            trigger: ".o_stock_barcode_main_menu",
            run: "scan WHINQCPRB",
        },
        {
            trigger: ".o_check_quality",
            run: "click",
        },
        // User Error appears as quality checks require lot/sn set for tracked products
        {
            trigger:
                ".modal-content.o_error_dialog:contains(You need to supply a Lot/Serial Number for product: - productserial1) .btn-close",
            run: "click",
        },
        {
            trigger: ".o_barcode_client_action",
            run: "scan productserial1",
        },
        {
            trigger: ".o_barcode_line.o_selected:contains(productserial1)",
            run: "scan SN001",
        },
        {
            trigger: ".o_barcode_line:contains(SN001)",
        },
        // Open QC's to check that only the one related to SN001 is todo
        {
            trigger: ".o_check_quality",
            run: "click",
        },
        // Discard the dialog and check that the validation process displays the same QC
        {
            trigger:
                ".modal-content:contains(productserial1):has(.o_field_widget[name=nb_checks]:contains(1)) .btn-close",
            run: "click",
        },
        {
            trigger: ".o_validate_page",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-header:contains('Incomplete Transfer')) button:contains('Create Backorder')",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-header:contains(productserial1)) button[name=do_pass]",
            run: "click",
        },
        {
            trigger: ".o_web_client:not(.modal-open) .o_validate_page",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-header:contains('Incomplete Transfer')) button:contains('Create Backorder')",
            run: "click",
        },
        {
            trigger: ".o_notification_bar.bg-success",
        },
    ],
});

registry.category("web_tour.tours").add("test_quality_check_packages_lots_tour", {
    steps: () => [
        // Scan product
        { trigger: ".o_barcode_client_action", run: "scan productlot1" },
        // First lot (2 units) -> Pack
        { trigger: ".o_barcode_line.o_selected", run: "scan lot-01" },
        { trigger: ".o_barcode_line .o_line_lot_name:contains(lot-01)" },
        { trigger: ".o_barcode_line .qty-done:contains(1)", run: "scan lot-01" },
        { trigger: "button.o_put_in_pack", run: "click" },
        // Wait for first pack to be applied before scanning next lot
        { trigger: ".o_barcode_line .result-package" },
        // Second lot (2 units) -> Pack
        { trigger: ".o_barcode_client_action", run: "scan lot-02" },
        {
            trigger: ".o_barcode_line.o_selected .o_line_lot_name:contains(lot-02)",
            run: "scan lot-02",
        },
        { trigger: "button.o_put_in_pack", run: "click" },
        // Wait for second pack to be applied before clicking quality checks
        { trigger: ".o_barcode_line:last-child .result-package" },
        // Validate picking -> pass quality checks popup
        { trigger: ".o_check_quality", run: "click" },
        {
            trigger:
                ".modal-content:has(.modal-header:contains('productlot1 - 2.0 Units - lot-01')) button[name=do_pass]",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-header:contains('productlot1 - 2.0 Units - lot-02')) button[name=do_pass]",
            run: "click",
        },
        // Final validation
        { trigger: ".o_validate_page", run: "click" },
        { trigger: ".o_notification_bar.bg-success" },
    ],
});

registry.category("web_tour.tours").add("test_operation_quality_check_kept_on_partial_barcode_exit", {
    steps: () => [
        // Receive 1 of the 2 units, then leave with the back button.
        { trigger: '.o_barcode_client_action', run: "scan product1" },
        { trigger: '.o_barcode_line span.qty-done:contains(1)' },
        { trigger: 'header.o_barcode_header button.o_exit', run: 'click' },
        { trigger: '.o_stock_barcode_main_menu' },
    ],
});
