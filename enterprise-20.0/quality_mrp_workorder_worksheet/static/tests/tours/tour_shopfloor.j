/** @odoo-module **/

import * as helper from "@mrp_workorder/../tests/tours/running_tour_action_helper";
import { stepUtils } from "@mrp_workorder/../tests/tours/tour_step_utils";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_worksheet_quality_check", {
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
                    steps: [
                        { label: "Lovely Operation", workcenter: "Lovely Workcenter" },
                    ],
                });
            }
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
                    steps: [
                        { label: "Lovely Worksheet" },
                    ],
                });
            }
        },
        {
            content: "Open the worksheet Quality Check",
            trigger: ".o_mrp_record_line button.o_btn_icon:has([data-icon='article'])",
            run: "click",
        },
        {
            trigger: ".modal-header .modal-title:contains(Lovely Worksheet)",
        },
        {
            trigger: "div.o_property_field_value input[type=checkbox]",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger:
                ".o_mrp_display_record .o_line_value.text-success:contains('passed')",
        },
        {
            content: "Check that the quality check has been validated",
            trigger: "button.btn-primary[barcode_trigger='CLMO']",
            run: "click",
        },
        { trigger: ".o_view_nocontent" },
    ],
});
