import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Custom field widget for the "Correct employee" link in attendance warnings.
 * Uses action.doAction to open the Employee form without triggering an automatic
 * form save/commit on the draft attendance record (which standard button type="object" does).
 */
class CorrectEmployeeButton extends Component {
    static template = "hr_attendance_gantt.CorrectEmployeeButton";
    props = useProps(standardFieldProps);

    setup() {
        this.action = useService("action");
    }

    onClick() {
        const employeeId = this.props.record.data.employee_id;
        if (employeeId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "hr.employee",
                res_id: employeeId.id,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }
}

export const correctEmployeeButton = {
    component: CorrectEmployeeButton,
};

registry.category("fields").add("correct_employee_button", correctEmployeeButton);
