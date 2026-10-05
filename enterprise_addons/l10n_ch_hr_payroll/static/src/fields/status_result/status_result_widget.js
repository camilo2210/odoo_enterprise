/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { SwissdecNotification } from "@l10n_ch_hr_payroll/components/swissdec_notification";
import { swissdecFormat } from "@l10n_ch_hr_payroll/components/swissdec_format";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class StatusResultWidget extends Component {
    props = useProps(standardFieldProps);
    static template = "l10n_ch_hr_payroll.StatusResultWidgetTemplate";
    static components = {
        SwissdecNotification,
    };

    setup() {
        this.format = swissdecFormat;
    }

    get parsedData() {
        return this.props.record.data[this.props.name];
    }

    /** Notifications of an accepted declaration, or the general warnings of a declaration. */
    get responseState() {
        const parsedData = this.parsedData;
        if (parsedData?.ResponseState) {
            return parsedData.ResponseState;
        }
        return parsedData?.Info || parsedData?.Warning ? parsedData : null;
    }

    /** Anything else is an error response. */
    get errorResponse() {
        return this.parsedData && !this.responseState ? this.parsedData : null;
    }
}

registry.category("fields").add("swissdec_status_result", {
    component: StatusResultWidget,
});

export default StatusResultWidget;
