
import { Component, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { payslipShowAllState } from "../views/payslip_form/hr_payslip_list_row_visibility_renderer";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

class PayslipShowAllToggle extends Component {
    static template = "hr_payroll.PayslipShowAllToggle";
    props = useProps(standardWidgetProps);

    state = payslipShowAllState;

    toggle() {
        this.state.showAll = !this.state.showAll;
        localStorage.setItem("hr_payroll.display_all_payslip_lines", this.state.showAll);
    }
}

registry.category("view_widgets").add("payslip_show_all_toggle", {
    component: PayslipShowAllToggle,
});
