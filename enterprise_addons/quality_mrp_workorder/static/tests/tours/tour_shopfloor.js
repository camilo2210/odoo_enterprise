/** @odoo-module **/

import * as helper from "@mrp_workorder/../tests/tours/running_tour_action_helper";
import { stepUtils } from "@mrp_workorder/../tests/tours/tour_step_utils";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_register_sn_production_quality_check", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Lovely Workcenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Check that we are in the MO view",
            trigger: ".o_work_center_btn.active:contains('Overview')",
            run: function () {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    product: "Lovely Product",
                    quantity: "1 Unit",
                    steps: [{ label: "Lovely Operation", workcenter: "Lovely Workcenter" }],
                });
            },
        },
        ...stepUtils.clickOnWorkcenterButton("Lovely Workcenter"),
        {
            trigger: ".o_work_center_btn.active:contains('Lovely Workcenter')",
            run: function () {
                helper.assertWorkOrderValues({
                    name: "TWH/MO/00001",
                    product: "Lovely Product",
                    operation: "Lovely Operation",
                    quantity: "1 Unit",
                    steps: [{ label: "Lovely Production Registering" }],
                });
            },
        },
        {
            content: "Register a new serial number",
            trigger: "button.o_btn_icon:has([data-icon='add'])",
            run: "click",
        },
        {
            trigger: ".modal-content [name='lot_producing_ids'] input",
            run: "edit SN0012",
        },
        {
            trigger:
                '.modal-content .o_field_widget[name=lot_producing_ids] .dropdown-item:contains(Create "SN0012")',
            run: "click",
        },
        { trigger: ".o_field_widget[name='lot_producing_ids'] span.o_tag[aria-label='SN0012']" },
        {
            trigger:
                ".modal-content:has(.modal-header:contains(Register Production: Lovely Product)) button:contains(Validate)",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record:has(.card-header:contains(Lovely Operation)) button:contains(Produce)",
        },
    ],
});

registry.category("web_tour.tours").add("test_shop_floor_spreadsheet", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Mountains"),
        ...stepUtils.confirmWorkcentersSelection(),
        ...stepUtils.clickOnWorkcenterButton("Mountains"),
        {
            content: "Start the workorder on header click",
            trigger: ".o_mrp_display_record .o_finished_product:contains('Snow leopard')",
            run: "click",
        },
        {
            content: "Open spreadsheet check action",
            trigger: ".o_mrp_display_record button.btn-primary.o_btn_icon:has([data-icon='grid_view'])",
            run: "click",
        },
        {
            content: "Ensure the spreadsheet is opened",
            trigger: ".o-spreadsheet",
        },
        {
            content: "Save the check result",
            trigger: ".o_main_navbar button.btn-primary",
            run: "click",
        },
        {
            content: "Ensure we're back on the Shop Floor",
            trigger: ".o_mrp_display",
        },
    ],
});

registry.category("web_tour.tours").add("test_quality_fail_message", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.addWorkcenterToDisplay("Assembly Workcenter"),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Open the workorder.",
            trigger: ".o_mrp_record_line i[data-icon='chevron_forward']",
            run: "click",
        },
        {
            content: "Fail the quality check.",
            trigger: ".o_mrp_record_line i[data-icon='close']",
            run: "click",
        },
        {
            content: "Press the Ok button on the failure message popup.",
            trigger: "button.btn-primary:contains('OK')",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("test_mass_produce_backorder_qc", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Ensure we are on Overview",
            trigger: ".o_work_center_btn:contains('Overview')",
        },
        {
            content: "Select the MO card to Register Production",
            trigger:
                ".o_mrp_display_record:contains('Serial Gadget') button:contains('Quality Checks')",
            run: "click",
        },
        {
            content: "Pass the Quality Check",
            trigger: ".modal-content button[name='do_pass']",
            run: "click",
        },
        {
            content: "Close the production for this unit",
            trigger: "button:contains('Produce')",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("test_backorder_qc_without_auto_close", {
    steps: () => [
        ...stepUtils.openWorkcentersSelector(),
        ...stepUtils.confirmWorkcentersSelection(),
        {
            content: "Ensure we are on Overview",
            trigger: ".o_work_center_btn:contains('Overview')",
        },
        {
            content: "Open the MO card to perform Quality Checks",
            trigger:
                ".o_mrp_display_record:contains('Serial Gadget') button:contains('Quality Checks')",
            run: "click",
        },
        {
            content: "Pass the Quality Check",
            trigger: ".modal-content button[name='do_pass']",
            run: "click",
        },
        {
            content: "Ensure there is no 'Produce' button",
            trigger:
                ".o_mrp_display_record:contains('Serial Gadget'):not(:has(button:contains('Produce')))",
        },
    ],
});
