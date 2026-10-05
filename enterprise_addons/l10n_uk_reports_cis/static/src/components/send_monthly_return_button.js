/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, usePlugin, useProps } from "@odoo/owl";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";
import { ORM } from "@web/core/orm_plugin";
import { UIPlugin } from "@web/core/ui/ui_plugin";


export class SendCISMonthlyReturnButton extends Component {
    /**
     * We need a custom widget as the password field is set as non stored.
     * The client side don't write the password from the field to the orm cache because of that.
     * 
     * The only way to pass the password to the function is by making a manual orm call, and manually passing it as parameter.
     */
    static template = "l10n_uk_cis.SendCISMonthlyReturn";
    props = useProps(standardWidgetProps);

    actionPlugin = usePlugin(ActionPlugin);
    orm = usePlugin(ORM);
    ui = usePlugin(UIPlugin);

    async sendMonthlyReturn() {
        this.ui.block();
        try {
            await this.orm.call("cis.monthly.return.wizard", "action_send_montlhy_return", [
                this.props.record.data.return_id.id,
                this.props.record.data.employment_status,
                this.props.record.data.subcontractor_verification,
                this.props.record.data.inactivity_indicator,
                this.props.record.data.hmrc_cis_password,
            ]);
            this.actionPlugin.doAction({
                type: "ir.actions.client",
                tag: "action_return_refresh",
                params: {
                    return_ids: [this.props.record.data.return_id.id],
                    next_action: { type: "ir.actions.act_window_close" },
                },
            });
        }
        finally {
            this.ui.unblock();
        }
    }
}
export const sendCISMonthlyReturnButton = {
    component: SendCISMonthlyReturnButton,
}
registry.category("view_widgets").add("send_cis_monthly_return_button", sendCISMonthlyReturnButton);
