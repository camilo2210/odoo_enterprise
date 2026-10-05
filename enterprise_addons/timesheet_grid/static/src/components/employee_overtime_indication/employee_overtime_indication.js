import { _t } from "@web/core/l10n/translation";
import { formatFloatTime } from "@web/views/fields/formatters";
import { formatFloat } from "@web/core/utils/numbers";

import { Component, useProps, t } from "@odoo/owl";

export const employeeOvertimeIndicationProps = {
    allocated_hours: t.number().optional(),
    uom: t.string().optional("hours"),
    worked_hours: t.number().optional(),
};

export class EmployeeOvertimeIndication extends Component {
    props = useProps(employeeOvertimeIndicationProps);
    static template = "timesheet_grid.EmployeeOvertimeIndication";

    get shouldShowHours() {
        return this.props.allocated_hours > 0;
    }

    get colorClasses() {
        if (!this.shouldShowHours) {
            return "";
        }
        return this.props.worked_hours < this.props.allocated_hours
            ? "text-danger"
            : "text-success";
    }

    get overtime() {
        return this.props.worked_hours - this.props.allocated_hours;
    }

    get overtimeIndication() {
        if (!this.shouldShowHours) {
            return null;
        }
        if (this.overtime === 0) {
            return null; // nothing to display
        }
        let overtimeIndication = this.overtime > 0 ? "+" : "";
        if (this.props.uom === "days") {
            // format in days
            overtimeIndication += formatFloat(this.overtime);
        } else {
            // format in hours
            overtimeIndication += formatFloatTime(this.overtime);
        }
        return overtimeIndication;
    }

    get title() {
        if (this.props.uom === "days") {
            return _t(
                "Difference between the number of days recorded (%(worked_hours)s) and the number of days the employee was supposed to work according to their contract (%(allocated_hours)s)",
                {
                    allocated_hours: this.props.allocated_hours,
                    worked_hours: this.props.worked_hours,
                }
            );
        }
        return _t(
            "Difference between the number of hours recorded (%(worked_hours)s) and the number of hours the employee was supposed to work according to their contract (%(allocated_hours)s)",
            {
                allocated_hours: this.props.allocated_hours,
                worked_hours: this.props.worked_hours,
            }
        );
    }
}
