import { Component, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { toDateOnly, formatDateLabel } from "@hr_payroll/components/dashboard/utils";

export class DashboardEmptyScreen extends Component {
    static template = "hr_payroll.DashboardEmptyScreen";

    props = useProps({
        closingDatesData: t.array(),
    });

    setup() {
        this.action = useService("action");
        this.toDateOnly = toDateOnly;
    }

    formatClosingDate(closingDate) {
        return formatDateLabel(luxon.DateTime.fromISO(closingDate));
    }

    gotoAllPayslips() {
        this.action.doAction("hr_payroll.action_view_hr_payslip_month_form");
    }
}
