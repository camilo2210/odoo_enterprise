/** @odoo-module **/

import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

/**
 * tour: a basic employee with NO payroll rights navigates
 * Employees → Employee Profile → Monthly Hours smart button → List view.
 *
 * This used to crash because the attendance controller loaded the payrun
 * layout, which required hr_payroll permissions.
 */
registry.category("web_tour.tours").add("test_attendance_access_no_payroll_rights", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Employees app",
            trigger: ".o_app[data-menu-xmlid='hr.menu_hr_root']",
            run: "click",
        },
        {
            content: "Open the employee profile",
            trigger: ".o_kanban_record:contains('test_employee')",
            run: "click",
        },
        {
            content: "Click the Monthly Hours smart button",
            trigger: ".oe_stat_button:contains('Monthly Hours')",
            run: "click",
        },
        {
            content: "Verify attendance list view loaded without errors",
            trigger: ".o_list_view:not(.o_error_dialog)",
        },
        {
            content: "Verify first week group header (W31)",
            trigger: ".o_group_header span.fw-bold:contains('9h')",
        },
        {
            content: "Verify second week group header (W32)",
            trigger: ".o_group_header span.fw-bold:contains('8h')",
        },
        stepUtils.goToUrl("/odoo/attendances"),
        {
            content: "Verify attendance gantt view loaded without errors",
            trigger: ".o_gantt_view:not(.o_error_dialog)",
        },
    ],
});
