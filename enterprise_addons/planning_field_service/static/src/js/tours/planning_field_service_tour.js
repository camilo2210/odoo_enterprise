import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add("planning_field_service_tour", {
    steps: () => [
        {
            trigger: ".o_app[data-menu-xmlid='planning.planning_menu_root']",
            content: markup(
                _t("<b>Start managing your onsite shifts</b><br/><i>Everything begins here.</i>")
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_gantt_button_add",
            content: markup(
                _t("<b>Create a shift</b><br/><i>Open the form to enter shift details.</i>")
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='resource_ids'] input",
            content: markup(
                _t(
                    "<b>Assign a resource</b><br/><i>Add multiple technicians or reserve equipment if needed.</i>"
                )
            ),
            tooltipPosition: "right",
            run: "click",
        },
        {
            isActive: ["auto"],
            trigger: ".o_field_widget[name='resource_ids'] input",
            run: "edit Worker",
        },
        {
            isActive: ["auto"],
            trigger: ".o-autocomplete--dropdown-item > a:contains('Worker')",
            run: "click",
        },
        {
            isActive: ["auto"],
            trigger: ".modal button.o_form_button_save",
            run: "click",
        },
        {
            trigger: "body:not(:has(.ui-autocomplete))",
        },
        {
            trigger: ".o_field_widget[name='partner_id'] input",
            content: markup(
                _t(
                    "<b>Select the customer</b><br/><i>Add an address to automatically generate directions.</i>"
                )
            ),
            tooltipPosition: "right",
            run: "click",
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:not(:has(i.oi))",
            run: "click",
        },
        {
            trigger: "body:not(:has(.ui-autocomplete))",
        },
        {
            trigger: "button[name='action_send']",
            content: markup(
                _t(
                    "<b>Publish the shift</b><br/><i>This officially schedules the shift and makes it visible to technicians.</i>"
                )
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_gantt_pill:not(.o_gantt_consolidated_pill)",
            content: markup(
                _t("<b>Select the shift</b><br/><i>You can view the details of the shift.</i>")
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_popover_footer button[name='action_sign_in']",
            content: markup(
                _t(
                    "<b>Start onsite</b><br/><i>Start the shift when you arrive at the customer location.</i>"
                )
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_gantt_pill:not(.o_gantt_consolidated_pill)",
            content: markup(
                _t("<b>Select the shift</b><br/><i>You can view the details of the shift.</i>")
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_popover_footer button[name='action_complete']",
            content: markup(
                _t(
                    "<b>Mark the shift as complete</b><br/><i>Close the shift once the work is finished.</i>"
                )
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
    ],
});
