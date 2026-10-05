import { t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { patch } from "@web/core/utils/patch";
import {
    EmployeeOvertimeIndication,
    employeeOvertimeIndicationProps,
} from "@timesheet_grid/components/employee_overtime_indication/employee_overtime_indication";

Object.assign(employeeOvertimeIndicationProps, {
    month: t.string().optional(),
    targetLimitsSet: t.boolean().optional(false),
});

patch(EmployeeOvertimeIndication.prototype, {
    get title() {
        const showTargetLeft = this.env.searchModel?.context?.show_target_left;
        if (showTargetLeft && this.props.targetLimitsSet) {
            if (this.props.uom === "days") {
                return _t("Difference between the number of billable days recorded in %(month)s (%(worked_hours)s) and the billing time target of the employee (%(allocated_hours)s)", {
                    allocated_hours: this.props.allocated_hours,
                    worked_hours: this.props.worked_hours,
                    month: this.props.month,
                });
            }
            return _t("Difference between the number of billable hours recorded in %(month)s (%(worked_hours)s) and the billing time target of the employee (%(allocated_hours)s)", {
                allocated_hours: this.props.allocated_hours,
                worked_hours: this.props.worked_hours,
                month: this.props.month,
            });
        }
        return super.title;
    },
});
