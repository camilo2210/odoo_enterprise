/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { SwissdecNotification } from "@l10n_ch_hr_payroll/components/swissdec_notification";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class StatusResultWidget extends Component {
    static template = "l10n_ch_hr_payroll.StatusResultWidgetTemplate";
    static components = {
        SwissdecNotification,
    };

    props = useProps(standardFieldProps);

    get parsedData() {
        return this.props.record.data[this.props.name];
    }

    get response_state() {
        const parsedData = this.parsedData;
        if (parsedData.ResponseState) {
            return parsedData.ResponseState;
        } else if (parsedData.Info || parsedData.Warning) {
            return parsedData;
        }
        return null;
    }

    get error() {
        const parsedData = this.parsedData;
        if (!parsedData.ResponseState && !parsedData.Info && !parsedData.Warning) {
            return parsedData;
        }
        return null;
    }
}

registry.category("fields").add("swissdec_status_result", {
    component: StatusResultWidget,
});

export default StatusResultWidget;
