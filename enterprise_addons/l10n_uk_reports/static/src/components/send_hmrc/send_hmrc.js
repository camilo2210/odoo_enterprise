import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, usePlugin, useProps } from "@odoo/owl";
import { retrieveHMRCClientInfo } from "../../hmrc_api";
import { ORM } from "@web/core/orm_plugin";
import { UIPlugin } from "@web/core/ui/ui_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

function isValidUuid(str) {
    return /^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$/i.test(str);
}

export class SendHmrcButton extends Component {
    static template = "l10n_uk_reports.SendHmrcButton";
    props = useProps(standardWidgetProps);

    actionPlugin = usePlugin(ActionPlugin);
    orm = usePlugin(ORM);
    ui = usePlugin(UIPlugin);

    title = _t('Send Data to the HMRC Service');
    hmrcGovClientDeviceIdentifier = this.props.record.data.hmrc_gov_client_device_id;

    async retrieveClientInfo() {
        this.ui.block();
        try {
            if (!localStorage.getItem('hmrc_gov_client_device_id')) {
                localStorage.setItem('hmrc_gov_client_device_id', this.hmrcGovClientDeviceIdentifier);
            }
            if (!isValidUuid(localStorage.getItem('hmrc_gov_client_device_id'))) {
                localStorage.removeItem('hmrc_gov_client_device_id');
            }
            let clientData = retrieveHMRCClientInfo();
            clientData.hmrc_gov_client_device_id = localStorage.getItem('hmrc_gov_client_device_id');
            await this.orm.call(
                'l10n_uk.vat.obligation',
                'action_submit_vat_return',
                [this.props.record.data.obligation_id.id, clientData],
                {context: this.props.record.context},
            );
            this.actionPlugin.doAction({'type': 'ir.actions.act_window_close'})
        } finally {
            this.ui.unblock();
            this.actionPlugin.doAction({
                type: "ir.actions.client",
                tag: "soft_reload",
            });
        }
    }
}

export const sendHmrcButton = {
    component: SendHmrcButton,
}

registry.category('view_widgets').add('send_hmrc_button', sendHmrcButton);
