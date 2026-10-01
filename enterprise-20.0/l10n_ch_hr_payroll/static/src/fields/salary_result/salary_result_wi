/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { SwissdecNotification } from "@l10n_ch_hr_payroll/components/swissdec_notification";
import { AccordionItem } from "@web/core/dropdown/accordion_item";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class SalaryResultWidget extends Component {
    static template = "l10n_ch_hr_payroll.SalaryResultWidgetTemplate";
    static components = {
        SwissdecNotification,
        AccordionItem,
    };

    props = useProps(standardFieldProps);

    get parsedData() {
        const { SalaryResult, Dialog } = this.props.record.data[this.props.name];
        const institution_domain = this.props.record.data["domain"];

        if (SalaryResult) {
            return SalaryResult[institution_domain];
        } else if (Dialog) {
            return Dialog[institution_domain];
        }
        return null;
    }
}

registry.category("fields").add("swissdec_salary_result", {
    component: SalaryResultWidget,
});

export default SalaryResultWidget;
