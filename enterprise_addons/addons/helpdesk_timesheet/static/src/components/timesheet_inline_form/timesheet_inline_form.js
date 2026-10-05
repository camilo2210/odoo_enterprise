import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { patch } from "@web/core/utils/patch";
import { TimesheetInlineForm } from "@timesheet_grid/components/timesheet_inline_form/timesheet_inline_form";

patch(TimesheetInlineForm.prototype, {
    get fieldNames() {
        return [...super.fieldNames, "has_helpdesk_team", "helpdesk_ticket_id"];
    },

    get activeFields() {
        const activeFields = super.activeFields;
        activeFields.helpdesk_ticket_id.context =
            "{'default_project_id': project_id, 'timesheet_timer_search': True, 'search_default_my_ticket': True, 'search_default_is_open': True, 'search_default_closed_on': 'custom_closed_on_today'}";
        activeFields.helpdesk_ticket_id.placeholder = "";
        return activeFields;
    },

    isFieldVisible(fieldInfo, record) {
        if (fieldInfo.name === "task_id") {
            const isVisible = !evaluateBooleanExpr(
                "has_helpdesk_team and not task_id",
                record.evalContextWithVirtualIds
            );
            return isVisible;
        }
        if (fieldInfo.name === "helpdesk_ticket_id") {
            const isVisible = !evaluateBooleanExpr(
                "not has_helpdesk_team and not helpdesk_ticket_id",
                record.evalContextWithVirtualIds
            );
            return isVisible;
        }
        return true;
    },
});
