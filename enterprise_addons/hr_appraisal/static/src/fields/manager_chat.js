import { Component, useProps } from "@odoo/owl";

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class AppraisalManagerChat extends Component {
    static template = "hr_appraisal.ManagerChat";
    props = useProps(standardWidgetProps);

    setup() {
        super.setup();
        this.store = useService("mail.store");
    }
}

export const appraisalManagerChat = { component: AppraisalManagerChat };
registry.category("view_widgets").add("appraisal_manager_chat", appraisalManagerChat);
