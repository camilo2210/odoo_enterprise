import { registry } from "@web/core/registry";
import { assert } from "@stock/../tests/tours/tour_helper";
import { stepUtils } from "./tour_step_utils";
import * as helper from "./running_tour_action_helper";

registry.category("web_tour.tours").add("test_shop_floor", {
    steps: () => [
        // SHOP FLOOR CONFIGURATION
        // Select the workcenter the first time we enter in shopfloor.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Jungle"),
        ...stepUtils.addWorkcenterToDisplay("Savannah"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            trigger: '.o_work_centers_container button.o_work_center_btn:contains("Jungle")',
            run() {
                helper.assertSearchFacets([{ value: "MO Ready" }]);
            },
        },
        // Select two employees: one by scanning her badge ID and one by clicking on him.
        ...stepUtils.openEmployeesList(),
        {
            content: "Scan Abbie Seedy's badge",
            trigger: ".modal-body .o_mrp_operatos_dialog",
            run: "scan 659898105101",
        },
        { trigger: ".o_mrp_operatos_dialog li[name='Abbie Seedy'].active" },
        ...stepUtils.addEmployee("Billy Demo"),
        // Confirm the employees' selection.
        { trigger: ".modal-footer button.btn-primary", run: "click" },
        { trigger: ".o_mrp_employees_panel li:contains(Billy Demo)", run: "click" },
        { trigger: ".o_mrp_employees_panel li:contains(Abbie Seedy):not(.o_admin_user)" },
        { trigger: ".o_mrp_employees_panel li:contains(Billy Demo).o_admin_user" },
        {
            content: "Go to workcenter Savannah from MO card",
            trigger: '.o_mrp_record_line .o_tag:contains("Savannah")',
            run: "click",
        },

        // PROCESS FIRST WORKORDER
        {
            trigger: '.o_work_centers_container button.active:contains("Savannah")',
            run() {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    operation: "Creation",
                    product: "Giraffe",
                    quantity: "2 Units",
                    steps: [
                        { label: "Register Production" },
                        { label: "Instructions" },
                        { label: "Register legs", value: "8 Units" },
                        { label: "Register necks", value: "2 Units" },
                        { label: "TWH/Stock / NE1", value: "1 Units" },
                        { label: "TWH/Stock / NE2", value: "1 Units" },
                        { label: "Release" },
                    ],
                });
            },
        },
        {
            content: "Start the workorder on header click",
            trigger: 'h5.o_finished_product:contains("Giraffe")',
            run: "click",
        },
        {
            content: "Register production check",
            trigger: ".o_mrp_record_line:contains('Register Production') .btn-primary",
            run: "click",
        },
        // Handle mrp.production.serials wizard
        {
            content: "Edit the quantity produced",
            trigger: ".o_mrp_register_production_dialog input.o_input",
            run: "edit 1.00",
        },
        {
            content: "Register production: Giraffe",
            trigger: ".o_workorder_bar_content:contains('Generate Lot') .btn-primary",
            run: "click",
        },
        {
            content: "Check if the button clear is visible",
            trigger: ".o_mrp_register_production_dialog .btn-secondary:contains('Clear')",
        },
        {
            content: "Check that the value is still 1.00 then Edit the quantity produced",
            trigger: ".o_mrp_register_production_dialog input.o_input:value(1.00)",
            run: "edit 2.00",
        },
        {
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        // Produced product's lot should be displayed and "Register Production" should be crossed.
        // "Register Production" should be crossed.
        { trigger: ".text-decoration-line-through:contains('Register Production')" },
        { trigger: ".o_line_value:contains('0000001')" },
        // Check the instruction then mark it as read.
        { trigger: ".o_mrp_record_line:nth-child(2) [data-icon='info']", run: "click" },
        {
            trigger:
                ".o_tablet_popups.o_worksheet_modal .o_tablet_instruction_note:contains(Create this giraffe with a lot of care !)",
        },
        {
            content: "Close the instruction popup",
            trigger: ".o_tablet_popups.o_worksheet_modal .modal-header .btn-close",
            run: "click",
        },
        {
            content: "Mark the instruction as read",
            trigger:
                ".o_web_client:not(.modal-open) .o_mrp_record_line:nth-child(2) [data-icon='check']",
            run: "click",
        },
        {
            content: "Register legs consumption by scanning product's barcode",
            trigger: ".o_mrp_record_line:nth-child(2) [data-icon='undo']",
            run: "scan PRODUCT_LEG",
        },
        { trigger: ".modal-content input.o_input:value(8)" },
        { trigger: ".modal-content footer.modal-footer button.btn-primary", run: "click" },
        { trigger: ".o_mrp_record_line:nth-child(3) .o_line_label.text-decoration-line-through" },
        {
            content: "Undo previous marked quantity",
            trigger: ".o_mrp_record_line:nth-child(3) .o_btn_icon [data-icon='undo']",
            run: "click",
        },
        {
            content: "Open add quantity to enter 10 units this time",
            trigger: ".o_mrp_record_line:nth-child(3) .o_btn_icon [data-icon='edit']",
            run: "click",
        },
        { trigger: ".modal-content input.o_input:value(8)", run: "edit 10" },
        { trigger: ".modal-content footer.modal-footer button.btn-primary", run: "click" },
        { trigger: ".o_line_value.text-danger .o_mrp_record_line_qty:contains(10 / 8)" },
        { trigger: ".o_mrp_record_line:nth-child(3) .o_line_label.text-decoration-line-through" },
        {
            content: "Register not tracked components and continue production",
            trigger: "body:not(:has(.modal)) .o_mrp_record_line:nth-child(4) [data-icon='check']",
            run: "click",
        },
        { trigger: ".o_mrp_record_line:nth-child(4) [data-icon='add']" },
        {
            content: "Complete last operation",
            trigger: ".o_mrp_record_line:nth-child(7) [data-icon='check']",
            run: "click",
        },
        { trigger: ".o_mrp_record_line:nth-child(7) [data-icon='undo']" },
        {
            content: "Close first operation",
            trigger: '.card-footer button[barcode_trigger="CLWO"]:contains(Mark as Done)',
            run: "click",
        },
        { trigger: ".o_work_center_btn:contains('Savannah) .o_tabular_nums:contains('0')" },

        // PROCESS SECOND WORKORDER
        ...stepUtils.clickOnWorkcenterButton("Jungle"),
        {
            trigger: ".o_mrp_display_record:not(.o_demo)",
            run() {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    operation: "Release",
                    product: "Giraffe",
                    quantity: "2 Units",
                });
            },
        },
        {
            content: "Start the second workorder",
            trigger: 'div.o_mrp_display_record:contains("Release") .card-header',
            run: "click",
        },
        {
            content: "Open the WO setting menu again",
            trigger: '.o_mrp_display_record:contains("Release") .card-footer button.o_btn_icon',
            run: "click",
        },
        {
            content: "Add an operation button",
            trigger: '.modal:not(.o_inactive_modal) button[name="addComponent"]',
            run: "click",
        },
        {
            content: "Ensure the catalog is opened",
            trigger: ".modal:not(.o_inactive_modal) .o_product_kanban_catalog_view",
        },
        {
            content: "search Color",
            trigger: ".modal-body .o_searchview_input",
            run: "edit color",
        },
        {
            trigger: ".o_searchview_autocomplete .o-dropdown-item.focus",
            run: "click",
        },
        {
            content: "Ensure the search is done",
            trigger: '.modal-body div.o_searchview_facet:contains("color")',
        },
        {
            trigger: '.modal-body:not(:has(article.o_kanban_record:not(:contains("Color"))))',
        },
        {
            trigger:
                '.modal article.o_kanban_record:contains("Color") button [data-icon="shopping_cart"]',
            run: "click",
        },
        {
            content: "Ensure the Color product is added",
            trigger: ".modal .o_product_catalog_quantity",
        },
        {
            content: "Close the catalog",
            trigger: ".modal-header .btn-close",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal)) .o_mrp_display_record .o_mrp_record_line",
            run() {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    operation: "Release",
                    product: "Giraffe",
                    quantity: "2 Units",
                    steps: [{ label: "Color", value: "1 Unit" }],
                });
            },
        },
        {
            content: "Pause the workorder by scanning the barcode",
            trigger: ".o_mrp_display_record.o_active",
            run: "scan OBTPAUS",
        },
        { trigger: ".o_mrp_display_record:not(.o_active)" },
        {
            content: "Close the WO's Manufacturing Order by scanning the barcode",
            trigger: ".card-footer button[barcode_trigger=CLMO]",
            run: "scan OBTCLMO",
        },
        {
            content: "Confirm the consumption warning",
            trigger: ".modal-dialog button[name='action_confirm']",
            run: "click",
        },
        { trigger: ".o_nocontent_help" },

        // CREATE NEW MO
        // Leave Shop Floor to create a new MO from the Manufacturing app.
        ...stepUtils.closeShopFloor(),
        {
            content: "Switch to Manufacturing",
            trigger: '.o_app[data-menu-xmlid="mrp.menu_mrp_root"]',
            run: "click",
        },
        {
            content: "Pick Production",
            trigger: '.o-dropdown[data-menu-xmlid="mrp.menu_mrp_manufacturing"]',
            run: "click",
        },
        {
            content: "Pick Manufacturing Orders",
            trigger: '.o-dropdown-item[data-menu-xmlid="mrp.menu_mrp_production_action"]',
            run: "click",
        },
        {
            content: "Create an MO",
            trigger: "button.o_list_button_add",
            run: "click",
        },
        {
            content: "Pick a product name",
            trigger: "input#product_id_0",
            run: "edit test_product",
        },
        {
            content: "Create the product",
            trigger: "a#product_id_0_0_0:contains('test_product')",
            run: "click",
        },
        {
            content: "Confirm MO creation",
            trigger: 'button[name="action_confirm"]',
            run: "click",
        },
        {
            content: "Open the Shop Floor directly from the MO",
            trigger: 'button[name="action_open_shop_floor"]',
            run: "click",
        },
        {
            content: "Check the default search filter (filtered by the current MO)",
            trigger: ".o_mrp_display_records",
            run() {
                helper.assertSearchFacets([
                    { label: "Manufacturing Order", value: "TWH/MO/00002" },
                ]);
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00002",
                    product: "test_product",
                    quantity: "1 Unit",
                });
            },
        },
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_menuitem[href='/odoo/shop-floor']", run: "click" },
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 1, active: true },
                    { name: "My WO", count: 0 },
                    { name: "Jungle", count: 0 },
                    { name: "Savannah", count: 0 },
                ]);
            },
        },
        // Leave Shop Floor before to end the tour.
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_apps" },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_disable_serial_create", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            trigger:
                ".o_mrp_record_line:contains('Product 2') .btn-outline-secondary [data-icon='add']",
            run: "click",
        },
        {
            trigger:
                ".modal-dialog:has(.modal-title:contains('Add line: Product 2')) .o_create_button:contains(New)",
            run: "click",
        },
        {
            trigger:
                ".modal-dialog:has(.modal-title:contains('Create Move Line for Product 2')) .o_field_many2one_selection input",
            run: "edit 00001",
        },
        {
            trigger: "li.o_m2o_dropdown_option_create a:contains('00001')",
            run: "click",
        },
        {
            trigger:
                ".modal-dialog:has(.modal-body:contains('You are not allowed to create or edit')) .btn:contains(Close)",
            run: "click",
        },
        {
            trigger:
                ".modal-dialog:has(.modal-title:contains('Create Move Line for Product 2')) .btn:contains(Discard)",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal-dialog))",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_auto_select_workcenter", {
    steps: () => [
        // Select 3 available Work Centers.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Preparation Table 1"),
        ...stepUtils.addWorkcenterToDisplay("Preparation Table 2"),
        ...stepUtils.addWorkcenterToDisplay("Furnace"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 2, active: true },
                    { name: "My WO", count: 0 },
                    { name: "Preparation Table 1", count: 1 },
                    { name: "Preparation Table 2", count: 0 },
                    { name: "Furnace", count: 1 },
                ]);
            },
        },
        // Exit the Shop Floor and re-open it: WC buttons should be the same.
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_menuitem[href='/odoo/shop-floor']", run: "click" },
        {
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 2, active: true },
                    { name: "My WO", count: 0 },
                    { name: "Preparation Table 1", count: 1 },
                    { name: "Preparation Table 2", count: 0 },
                    { name: "Furnace", count: 1 },
                ]);
            },
        },
        // Finally check selectedWorkCenter preserved when coming back to Shop Floor via breadcrumbs
        ...stepUtils.clickOnWorkcenterButton("Furnace"),
        { trigger: ".o_mrp_display_record .card-footer button.o_btn_icon", run: "click" },
        { trigger: 'button[name="openMO"]', run: "click" },
        // In the MO form view, click the breadcrumb “Shop Floor”, to go back to ShopFloor
        { trigger: ".o_breadcrumb a:contains('Shop Floor')", run: "click" },
        {
            content: "Check the active Work-Center is Furnace",
            trigger: ".o_work_centers",
            run: () => {
                helper.assertWorkcenterButtons([
                    { name: "Overview", count: 2 },
                    { name: "My WO", count: 0 },
                    { name: "Preparation Table 1", count: 1 },
                    { name: "Preparation Table 2", count: 0 },
                    { name: "Furnace", count: 1, active: true },
                ]);
            },
        },
        // Exit the Shop Floor and open it from a WO form view.
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_menuitem[href='/odoo/work-centers']", run: "click" },
        { trigger: "button[data-menu-xmlid='mrp.menu_mrp_manufacturing']", run: "click" },
        { trigger: "a[data-menu-xmlid='mrp.menu_mrp_workorder_todo']", run: "click" },
        { trigger: ".o_data_cell[name='workcenter_id']:text(Furnace)", run: "click" },
        { trigger: "button[name='action_open_mes']", run: "click" },
        // Check whatever was selected, when we come from a WO form view, only its WC is displayed.
        {
            trigger: ".o_action.o_mrp_display",
            run: () => {
                helper.assertWorkcenterButtons([{ name: "Furnace", count: 1, active: true }]);
            },
        },
        {
            content: "Start the workorder",
            trigger:
                ".o_mrp_display_record:contains(TWH/MO/00001):not(:has(.o_active)) .o_mrp_display_record_start_btn",
            run: "click",
        },
        {
            content: "Check that the default search filter is set to the current MO",
            trigger: ".o_mrp_display_record:contains(TWH/MO/00001).o_active",
            run() {
                helper.assertSearchFacets([
                    { label: "Manufacturing Order", value: "TWH/MO/00001" },
                ]);
            },
        },
        {
            content: "Scan the operation",
            trigger: ".o_mrp_display_records",
            run: "scan bake it lovely",
        },
        {
            content: "Check the default search filter has been removed",
            trigger: ".o_mrp_display_record:contains(TWH/MO/00002)",
            run() {
                helper.assertSearchFacets([]);
            },
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_workcenter_barcode_refresh", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Lovecenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Check the work center is not the active one",
            trigger:
                ".o_work_centers_container button.o_work_center_btn:contains('Lovecenter'):not(.active)",
        },
        {
            content: "Scan the work center's old (stale) barcode: it shouldn't select it anymore",
            trigger: ".o_work_centers",
            run: "scan OLDBARCODE",
        },
        {
            content: "Check the work center is now the active one",
            trigger:
                ".o_work_centers_container button.o_work_center_btn:contains('Lovecenter').active",
        },
        ...stepUtils.closeShopFloor(),
        // Change the work center's barcode in the backend.
        {
            content: "Open MRP",
            trigger: "a.o_app:contains('Manufacturing')",
            run: "click",
        },
        {
            content: "Show Dropdown Configuration",
            trigger: "nav.o_main_navbar div.o_menu_sections button:contains('Configuration')",
            run: "click",
        },
        {
            content: "Open Work Centers",
            trigger: ".o-navigable[role='menuitem']:contains('Work Centers')",
            run: "click",
        },
        {
            content: "Open Lovecenter",
            trigger:
                ".o_list_view table tbody tr td.o_field_cell.o_list_char:contains('Lovecenter')",
            run: "click",
        },
        {
            content: "Edit barcode",
            trigger: ".o_form_view input#barcode_0",
            run: "edit NEWBARCODE",
        },
        {
            content: "Save",
            trigger: ".o_form_status_indicator button.o_form_button_save",
            run: "click",
        },
        {
            content: "Return to main menu",
            trigger: "nav.o_main_navbar a[href='/odoo']",
            run: "click",
        },
        ...stepUtils.openShopFloor(),
        ...stepUtils.clickOnWorkcenterButton("Overview"),
        {
            content: "Check the work center is not the active one",
            trigger:
                ".o_work_centers_container button.o_work_center_btn:contains('Lovecenter'):not(.active)",
        },
        {
            content: "Scan the work center's barcode",
            trigger: ".o_work_centers",
            run: "scan NEWBARCODE",
        },
        {
            content: "Check the work center is now the active one",
            trigger:
                ".o_work_centers_container button.o_work_center_btn:contains('Lovecenter').active",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_my_wo_filter_with_pin_user", {
    steps: () => [
        // Select the right workcenter.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Winter's Workshop"),
        ...stepUtils.confirmWorkcentersSelection(),
        // Open the employee panel and add both employees.
        { trigger: 'button.o_work_center_btn:contains("Winter\'s Workshop")' },
        ...stepUtils.openEmployeesList(),
        ...stepUtils.addEmployee("John Snow"),
        ...stepUtils.addEmployee("Queen Elsa"),
        { trigger: ".modal-footer button.btn-primary", run: "click" },
        // Select the first one => The employee is selected.
        {
            trigger: ".o_mrp_employees_panel li:contains('John Snow'):not(.o_admin_user)",
            run: "click",
        },
        { trigger: ".o_mrp_employees_panel li:contains('John Snow').o_admin_user" },
        // Select the second one => Her PIN code must be entered before to be selected.
        {
            trigger: ".o_mrp_employees_panel li:contains('Queen Elsa'):not(.o_admin_user)",
            run: "click",
        },
        ...stepUtils.enterPIN("41213"),
        { trigger: ".o_mrp_employees_panel li.o_admin_user:contains('Queen Elsa')" },
        ...stepUtils.clickOnWorkcenterButton("Winter's Workshop"),
        {
            content: "Start the first WO with the second employee",
            trigger: ".o_mrp_display_record:contains(TWH/MO/00001) .card-title",
            run: "click",
        },
        { trigger: ".o_mrp_display_record:contains(TWH/MO/00001).o_active" },
        { trigger: ".o_mrp_employees_panel li:contains(John Snow)", run: "click" },
        { trigger: ".o_admin_user:contains(John Snow)" },
        {
            content: "Start the second WO with the first employee",
            trigger: ".o_mrp_display_record:contains(TWH/MO/00002) .card-title",
            run: "click",
        },

        { trigger: ".o_mrp_display_record:contains('TWH/MO/00002').o_active" },
        ...stepUtils.clickOnWorkcenterButton("My WO"),
        // Check the right WO is displayed.
        {
            trigger:
                ".o_mrp_display_content:not(:has(.o_mrp_display_record:contains(TWH/MO/00001)))",
            run: () => {
                const currentEmployeeEl = document.querySelector(".o_admin_user div span.fw-bold");
                assert(currentEmployeeEl.innerText, "John Snow");
                const records = helper.getRecords();
                assert(records.length, 1);
                helper.assertWorkOrderValues({
                    index: 0,
                    name: "TWH/MO/00002",
                    operation: "Build the Snowman",
                    product: "Snowman",
                    quantity: "5 Units",
                    steps: [
                        { label: "Snowball", value: "15 Units" },
                        { label: "Carrot", value: "5 Units" },
                    ],
                });
            },
        },
        // Select the second employee and check only the right WO is shown.
        { trigger: ".o_mrp_employees_panel li:contains(Queen Elsa)", run: "click" },
        ...stepUtils.enterPIN("41213"),
        { trigger: ".o_admin_user:contains(Queen Elsa)" },
        {
            trigger: ".o_mrp_display_record:contains(TWH/MO/00001)",
            run: () => {
                const currentEmployeeEl = document.querySelector(".o_admin_user div span.fw-bold");
                assert(currentEmployeeEl.innerText, "Queen Elsa");
                const records = helper.getRecords();
                assert(records.length, 1);
                helper.assertWorkOrderValues({
                    index: 0,
                    name: "TWH/MO/00001",
                    operation: "Build the Snowman",
                    product: "Snowman",
                    quantity: "3 Units",
                    steps: [
                        { label: "Snowball", value: "9 Units" },
                        { label: "Carrot", value: "3 Units" },
                    ],
                });
            },
        },
        // Select again the first employee and check again only its WO is displayed.
        { trigger: ".o_mrp_employees_panel li:contains(John Snow)", run: "click" },
        { trigger: ".o_admin_user:contains(John Snow)" },
        {
            trigger: ".o_mrp_display_record:contains(TWH/MO/00002)",
            run: () => {
                const currentEmployeeEl = document.querySelector(".o_admin_user div span.fw-bold");
                assert(currentEmployeeEl.innerText, "John Snow");
                const records = helper.getRecords();
                assert(records.length, 1);
                helper.assertWorkOrderValues({
                    index: 0,
                    name: "TWH/MO/00002",
                    operation: "Build the Snowman",
                    product: "Snowman",
                    quantity: "5 Units",
                    steps: [
                        { label: "Snowball", value: "15 Units" },
                        { label: "Carrot", value: "5 Units" },
                    ],
                });
            },
        },
    ],
});

registry.category("web_tour.tours").add("test_generate_serials_in_shopfloor", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Assembly Line"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Assembly Line"),
        {
            content: "Start the workorder",
            trigger: ".o_mrp_display_record:not(o_active) .card-header",
            run: "click",
        },
        { trigger: ".o_mrp_display_record.o_active" },
        {
            content: "Open the by-product wizard",
            trigger: ".o_mrp_record_line:contains('By-product: byprod')",
            run: "click",
        },
        {
            content: "Input a serial",
            trigger: ".o_field_many2one[name='lot_id'] input",
            run: "edit 00001",
        },
        {
            content: "Generate the serials",
            trigger: "li.o_m2o_dropdown_option_create a",
            run: "click",
        },
        {
            content: "Save and close the wizard",
            trigger: ".modal-footer button.o_form_button_save",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record .o_mrp_record_line .o_line_label.text-decoration-line-through:contains('By-product: byprod')",
        },
        {
            trigger: ".o_mrp_record_line:contains('By-product: By Product 1')",
            run: "click",
        },
        {
            trigger: ".o_field_many2one[name='lot_id'] input",
            run: "edit 00002",
        },
        {
            trigger: "li.o_m2o_dropdown_option_create a",
            run: "click",
        },
        {
            trigger: ".modal-footer button.o_form_button_save",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record .o_mrp_record_line .o_line_label.text-decoration-line-through:contains('By-product: By Product 1')",
        },
        {
            content: "Set production as done",
            trigger: ".card-footer button.btn-primary[barcode_trigger='CLMO']",
            run: "click",
        },
        { trigger: ".o_view_nocontent" },
    ],
});

registry.category("web_tour.tours").add("test_byproduct_serial_with_prefill_lots", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Assembly Line"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Assembly Line"),
        {
            content: "Start the workorder",
            trigger: ".o_mrp_display_record:not(o_active) .card-header",
            run: "click",
        },
        { trigger: ".o_mrp_display_record.o_active" },
        {
            content: "Check that the by-product has no pre-filled indented lines",
            trigger:
                ".o_mrp_record_line:last-child:not(.o_mrp_record_line_indented):contains('By-product: byprod')",
        },
        {
            content: "Open the by-product wizard",
            trigger: ".o_mrp_record_line:contains('By-product: byprod')",
            run: "click",
        },
        {
            content: "Input a serial",
            trigger: ".o_field_many2one[name='lot_id'] input",
            run: "edit 00001",
        },
        {
            content: "Generate the serials",
            trigger: "li.o_m2o_dropdown_option_create a",
            run: "click",
        },
        {
            content: "Save and close the wizard",
            trigger: ".modal-footer button.o_form_button_save",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record .o_mrp_record_line .o_line_label.text-decoration-line-through:contains('By-product: byprod')",
        },
        {
            content: "Set production as done",
            trigger: ".card-footer button.btn-primary[barcode_trigger='CLMO']",
            run: "click",
        },
        { trigger: ".o_view_nocontent" },
    ],
});

registry.category("web_tour.tours").add("test_partial_backorder_with_multiple_operations", {
    steps: () => [
        {
            trigger: ".o_data_row:contains('MOBACK-002') td.o_data_cell",
            run: "click",
        },
        {
            trigger: 'button[name="action_open_shop_floor"]',
            run: "click",
        },
        // Make sure workcenter is available.
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Assembly Line"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            trigger: ".o_searchview_facet:last:contains(MOBACK-002)",
        },
        {
            content: "Select workcenter",
            trigger: 'button.btn-light:contains("Assembly Line")',
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) .o_quantity:contains(3 Units)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) .o_quantity:contains(5 Units)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) button:contains(Produce)",
        },
        // Refresh the view to make sure the filter is updated.
        {
            trigger: 'button.btn-light:contains("Overview")',
            run: "click",
        },
        {
            trigger: '.o_mrp_record_line:has(.o_tag:contains("Assembly Line"))',
        },
        {
            trigger: 'button.btn-light:contains("Assembly Line"):has(span:contains("1"))',
            run: "click",
        },
        {
            trigger: ".o_mrp_display_record_start_btn",
        },
        {
            trigger: ".o_searchview_facet:last:contains(MOBACK-002)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) button:contains(Produce)",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("test_change_qty_produced", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Lovecenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Lovecenter"),
        {
            content: "Register the production (automatically set it as 5/5 Units produced)",
            trigger: ".o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            content: "Handle MrpRegisterProductionDialog",
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        {
            content: "Open the wizard and decrease the produced quantity",
            trigger:
                ".o_mrp_record_line .text-decoration-line-through:contains('Register Production')",
            run: "click",
        },
        {
            content: "Edit the quantity producing",
            trigger: 'input[inputmode="decimal"]',
            run: "edit 3",
        },
        {
            content: "Validate",
            trigger: 'button.btn-primary:contains("Validate")',
            run: "click",
        },
        {
            content: "Waiting modal to close",
            trigger: "body:not(:has(.o_dialog))",
        },
        {
            content: "Mark the WorkOrder as Done",
            trigger: 'button.btn-secondary:contains("Produce")',
            run: "click",
        },
        {
            content: "Confirm consumption warning",
            trigger: 'button.btn-primary:contains("Confirm")',
            run: "click",
        },
        {
            content: "Dismiss backorder",
            trigger: 'button.btn-secondary:contains("Close Production")',
            run: "click",
        },
        {
            content: "Confirm consumption warning",
            trigger: 'button.btn-primary:contains("Confirm")',
            run: "click",
        },
        {
            content: "Check that there are no open work orders",
            trigger: ".o_nocontent_help",
        },
    ],
});

registry.category("web_tour.tours").add("test_mrp_manual_consumption_in_shopfloor", {
    steps: () => [
        {
            trigger: ".form-check:has(input[name='Nuclear Workcenter'])",
            run: "click",
        },
        {
            trigger: '.form-check:has(input[name="Nuclear Workcenter"]:checked)',
        },
        {
            trigger: "button:contains('Confirm')",
            run: "click",
        },
        {
            trigger: "button.btn-light:contains('Nuclear Workcenter')",
            run: "click",
        },
        {
            trigger: ".o_control_panel button.active:contains('Nuclear Workcenter')",
        },
        {
            trigger: "span.o_finished_product:contains('Finish')",
            run: "click",
        },
        {
            trigger: ".o_mrp_display_record.o_active",
        },
        {
            trigger: ".o_mrp_record_line:not(.text-muted) span:contains('Component')",
        },
    ],
});

registry.category("web_tour.tours").add("test_component_registration_on_split_productions", {
    steps: () => [
        ...stepUtils.addWorkcenterToDisplay("Lovely Workcenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Swap to the WO view of the Lovely Workcenter",
            trigger: ".o_control_panel button:contains(Lovely Workcenter)",
            run: "click",
        },
        {
            content: "Open register production",
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) .accordion button:contains('Instructions')",
            run: "click",
        },
        {
            trigger: ".o_data_row:contains(SN002) .o_list_record_remove button",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN001)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id'] input",
            run: "edit SN003",
        },
        {
            trigger: ".dropdown-item:contains(SN003)",
            run: "click",
        },
        {
            trigger: ".modal-content .modal-header",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN003)",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Check that the component registration has been completed",
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) button:contains(Mark as Done)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) .o_mrp_record_line:contains(Register Production) button[data-icon='add']",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) .o_mrp_record_line:has(.text-decoration-line-through:contains(Register Production)) span:contains(00)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO1)) button:contains(Close Production)",
            run: "click",
        },
        {
            content: "Check that the production was splitted",
            trigger: ".o_mrp_display_record:has(.card-title:contains(SMO1-002))",
        },
        // Process the operations for SMO2 in reverse order and consume more than expected
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) .o_mrp_record_line:contains(Register Production) button[data-icon='add']",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) .o_mrp_record_line:has(.text-decoration-line-through:contains(Register Production)) span:contains(00)",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) .accordion button:contains('Instructions')",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN004)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id'] input",
            run: "edit SN006",
        },
        {
            trigger: ".dropdown-item:contains(SN006)",
            run: "click",
        },
        {
            trigger: ".modal-content .modal-header",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN006)",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:not(:contains(SN006))",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id'] input",
            run: "edit SN005",
        },
        {
            trigger: ".dropdown-item:contains(SN005)",
            run: "click",
        },
        {
            trigger: ".modal-content .modal-header",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name='quant_id']:contains(SN005)",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(SMO2)) button:contains(Close Production)",
            run: "click",
        },
        {
            trigger:
                ".modal-content:has(.modal-title:contains(Consumption Warning)) button[name=action_confirm]",
            run: "click",
        },
        {
            content: "Check that the production was splitted",
            trigger: ".o_mrp_display_record:has(.card-title:contains(SMO2-002))",
        },
    ],
});

registry.category("web_tour.tours").add("test_operator_assigned_to_all_work_orders", {
    steps: () => [
        // Select workcenter for the station
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        //Open the employee panel, select Anita Olivier, close the selector
        ...stepUtils.openEmployeesList(),
        ...stepUtils.addEmployee("Anita Olivier"),
        { trigger: ".modal-footer button.btn-primary", run: "click" },
        // Select Anita Olivier in the side panel
        { trigger: ".o_mrp_employees_panel li:contains(Anita Olivier)", run: "click" },
        { trigger: ".o_mrp_employees_panel li:contains(Anita Olivier).o_admin_user" },
        // Switch to Workcenter1
        ...stepUtils.clickOnWorkcenterButton("Workcenter1"),
        // Complete both operations
        {
            trigger:
                ".o_mrp_display_record:has(.card-header:contains(OP1)) button:contains(Mark as Done)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-header:contains(OP2)) button:contains(Produce)",
            run: "click",
        },
        { trigger: ".o_nocontent_help" },
    ],
});

registry.category("web_tour.tours").add("test_automatic_backorder_no_redirect", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        // Switch to Workcenter1
        ...stepUtils.clickOnWorkcenterButton("Workcenter1"),
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK)) .o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            trigger: ".modal-content .o_field_widget[name=qty_done] input",
            run: "edit 1",
        },
        {
            trigger: ".modal-content button:contains(Validate)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK)) button:contains(Produce)",
            run: "click",
        },
        {
            trigger: ".o_mrp_display_record:has(.card-title:contains(MOBACK-002))",
            run: () => {
                const records = [...document.querySelectorAll(".o_mrp_display_record")].filter(
                    (rec) => rec.querySelector(".card-title").innerText.includes("MOBACK")
                );
                assert(records.length, 1);
            },
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) .o_mrp_record_line:contains(Register Production)",
            run: "click",
        },
        {
            trigger: ".modal-content button:contains(Validate)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-title:contains(MOBACK-002)) button:contains(Produce)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display:not(:has(.o_mrp_display_record:has(.card-title:contains(MOBACK))))",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_access", {
    steps: () => [
        {
            trigger: ".o_app:contains(Shop Floor)",
            run: "click",
        },
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.openEmployeesList(),
        {
            content: "scan a badge",
            trigger: ".modal-body .o_mrp_operatos_dialog",
            run: "scan 659898105101",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_unsynced_bom", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("WorkCenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("WorkCenter"),
        {
            content: "Find the COMP1 line",
            trigger: '.o_mrp_record_line:contains("COMP1")',
        },
        {
            content: "Mark the WorkOrder as Done",
            trigger: 'button.btn-secondary:contains("Mark as Done")',
            run: "click",
        },
        {
            content: "Check if the COMP2 line appeared",
            trigger: '.o_mrp_record_line:contains("COMP2")',
        },
        {
            content: "Register the production (automatically set it as 5/5 Units produced)",
            trigger: ".o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            content: "Handle MrpRegisterProductionDialog",
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        {
            content: "Close the production order",
            trigger: 'button.btn-secondary:contains("Produce")',
            run: "click",
        },
        {
            content: "Confirm consumption warning",
            trigger: 'button.btn-primary:contains("Confirm")',
            run: "click",
        },
        {
            content: "Check that there are no open work orders",
            trigger: ".o_nocontent_help",
        },
    ],
});

registry.category("web_tour.tours").add("test_product_consumption", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter1"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Workcenter1"),
        {
            content: "Click on consumption button",
            trigger: ".o_mrp_record_line button.btn [data-icon='add']",
            run: "click",
        },
        {
            content: "Check lot from TWH2 warehouse is not visible in the list",
            trigger: "table.o_list_table:not(:has([data-tooltip='TWH2/Stock']))",
        },
        {
            content: "Select first lot",
            trigger: ".o_data_row .o_data_cell:text(Lot 1)",
            run: "click",
        },
        {
            content: "Close the production order",
            trigger: 'button.btn-primary:contains("Produce")',
            run: "click",
        },
        {
            content: "Check that there are no open work orders",
            trigger: ".o_nocontent_help",
        },
    ],
});

registry.category("web_tour.tours").add("test_add_component_from_shop_floor", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Lovecenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Check that we are in the MO view",
            trigger:
                ".o_mrp_display_record:contains('First Love') .o_mrp_record_line:contains(Lovecenter)",
        },
        {
            content: "Add Product 1 to the MO components",
            trigger: ".o_mrp_display_record:contains('First Love') .card-footer button.o_btn_icon",
            run: "click",
        },
        {
            trigger: ".modal:not(.o_inactive_modal) button[name=addComponent]",
            run: "click",
        },
        {
            content: "Ensure the catalog is opened",
            trigger: ".modal:not(.o_inactive_modal) .o_product_kanban_catalog_view",
        },
        {
            trigger: ".modal-content .o_kanban_record:contains('Product 1')",
            run: "click",
        },
        {
            content: "Await for the Component to be added",
            trigger:
                ".modal-content .o_kanban_record:contains('Product 1') .o_product_catalog_quantity",
        },
        {
            trigger: ".modal-content button.btn-close",
            run: "click",
        },
        {
            content: "Check that the Product 1 are visible on the MO",
            trigger:
                ".o_mrp_display_record:contains('First Love') .o_mrp_record_line:contains('Product 1')",
        },
        {
            content: "Swap to the WO view of the Lovecenter",
            trigger:
                ".o_mrp_display_record:contains('First Love') .o_mrp_record_line:contains(Lovecenter)",
            run: "click",
        },
        {
            content: "Check that we are in the WO view",
            trigger: ".o_mrp_display_record:contains('First Love') .o_mrp_display_record_start_btn",
        },
        {
            content: "Add Product 2 to the WO components",
            trigger: ".o_mrp_display_record:contains('First Love') .card-footer button.o_btn_icon",
            run: "click",
        },
        {
            trigger: ".modal:not(.o_inactive_modal) button[name=addComponent]",
            run: "click",
        },
        {
            content: "Ensure the catalog is opened",
            trigger: ".modal:not(.o_inactive_modal) .o_product_kanban_catalog_view",
        },
        {
            trigger: ".modal-content .o_kanban_record:contains('Product 2')",
            run: "click",
        },
        {
            content: "Await for the Component to be added",
            trigger:
                ".modal-content .o_kanban_record:contains('Product 2') .o_product_catalog_quantity",
        },
        {
            content: "Add some Product 1 once more",
            trigger: ".modal-content .o_kanban_record:contains('Product 1')",
            run: "click",
        },
        {
            trigger:
                ".modal-content .o_kanban_record:contains('Product 1') div[name=o_kanban_qty_available_and_on_hand]:contains(8)",
        },
        {
            trigger: ".modal-content button.btn-close",
            run: "click",
        },
        {
            content: "Check that the Product 2 are visible on the WO",
            trigger:
                ".o_mrp_display_record:contains('First Love') .o_mrp_record_line:contains('Product 2')",
        },
    ],
});

registry.category("web_tour.tours").add("test_scrap_component_from_shopfloor", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Workcenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Workcenter"),
        {
            content: "Open the WO setting menu",
            trigger:
                '.o_mrp_display_record:contains("Component Consumption") .card-footer button.o_btn_icon',
            run: "click",
        },
        {
            content: "Open the scrap dialog",
            trigger: '.modal:not(.o_inactive_modal) button[name="action_scrap"]',
            run: "click",
        },
        {
            content: "Ensure that scrap modal is opened",
            trigger: '.modal:not(.o_inactive_modal) .modal-header:contains("Scrap Products")',
        },
        {
            content: "Add a product name",
            trigger: "input#product_id_0",
            run: "edit component",
        },
        {
            content: "Select the product",
            trigger: 'a#product_id_0_0_0:contains("component")',
            run: "click",
        },
        {
            content: "Edit the quantity",
            trigger: 'input[inputmode="decimal"]',
            run: "edit 1",
        },
        {
            content: "Confirm the scrap operation",
            trigger: '.modal:not(.o_inactive_modal) button[name="action_scrap"]',
            run: "click",
        },
        {
            content: "Verify that scrap success notification is displayed",
            trigger:
                '.o_notification_content:contains("The scrap order has been successfully registered.")',
        },
        ...stepUtils.closeShopFloor(),
        { trigger: ".o_apps" },
    ],
});

registry.category("web_tour.tours").add("test_barcode_scan_returns_stock_quant_not_vendor_quant", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Assembly"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Assembly"),
        {
            content: "Start the workorder",
            trigger: ".o_mrp_display_record:not(.o_active) .card-header",
            run: "click",
        },
        {
            content: "Open the Hand Piece component registration dialog",
            trigger:
                ".o_mrp_display_record.o_active .o_mrp_record_line:contains('Hand Piece') .o_btn_icon [data-icon='add']",
            run: "click",
        },
        {
            content: "Scan serial number barcode SN-TEST-001",
            trigger: ".o_dialog .o_list_table",
            run: "scan SN-TEST-001",
        },
        {
            content: "Verify Hand Piece component is marked as consumed",
            trigger:
                ".o_mrp_display_record.o_active .o_mrp_record_line:contains('Hand Piece') .o_line_label.text-decoration-line-through",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_workorders_sorting", {
    steps: () => [
        {
            trigger: "body",
            run: () => {
                // remove MOs from cache to force load and sort
                localStorage.clear();
            },
        },
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("WC Sorting"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("WC Sorting"),
        {
            trigger: ".o_work_centers",
            run: () => {
                const workorders = Array.from(document.querySelectorAll(".o_mrp_display_record"));
                const names = workorders.map(
                    (el) => el.querySelector(".o_mrp_display_name").innerText
                );
                if (names[0] !== "MO_PLANNED" || names[1] !== "MO_UNPLANNED") {
                    console.error("Wrong sorting, got " + names.join(", "));
                } else {
                    document.body.classList.add("sort-test-passed");
                }
            },
        },
        {
            trigger: "body.sort-test-passed",
        },
    ],
});

registry.category("web_tour.tours").add("test_continuous_bom_change_qty_produced", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Lovecenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Lovecenter"),
        {
            content: "Register the production (automatically set it as 5/5 Units produced)",
            trigger: ".o_mrp_record_line:contains('Register Production')",
            run: "click",
        },
        {
            content: "Handle MrpRegisterProductionDialog",
            trigger: ".btn-primary:contains('Validate')",
            run: "click",
        },
        {
            content: "Open the wizard to attempt decreasing the produced quantity",
            trigger:
                ".o_mrp_record_line .text-decoration-line-through:contains('Register Production')",
            run: "click",
        },
        {
            content:
                "Edit the quantity producing (should be ignored by continuous BoM backend logic)",
            trigger: 'input[inputmode="decimal"]',
            run: "edit 3",
        },
        {
            content: "Validate",
            trigger: 'button.btn-primary:contains("Validate")',
            run: "click",
        },
        {
            content: "Waiting modal to close",
            trigger: "body:not(:has(.o_dialog))",
        },
        {
            content: "Mark the WorkOrder as Done",
            trigger: 'button.btn-secondary:contains("Produce")',
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("test_gear_disabled_during_open_mo", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Nuclear Workcenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Wait for two WO cards to appear",
            trigger: ".o_mrp_display_records:has(.o_mrp_display_record:nth-child(2))",
        },
        {
            content: "Open menu on the first WO card",
            trigger: ".o_mrp_display_record:nth-child(1) .card-footer button.o_btn_icon",
            run: "click",
        },
        {
            content: "Click Open Manufacturing Order",
            trigger: 'button[name="openMO"]',
            run: "click",
        },
        {
            content: "Click three dots on the other WO card while navigation is pending",
            trigger: ".o_mrp_display_record:nth-child(2) .card-footer button.o_btn_icon",
            run: "click",
        },
        {
            content: "Verify the menu did not open on the other card while navigation was pending",
            trigger: "body:not(:has(.o_mrp_menu_dialog)) .o_mrp_display_record:nth-child(2)",
        },
        {
            content: "Verify navigation completed and MO form view is loaded",
            trigger: ".o_form_view .o_field_widget[name='product_id']",
        },
    ],
});
