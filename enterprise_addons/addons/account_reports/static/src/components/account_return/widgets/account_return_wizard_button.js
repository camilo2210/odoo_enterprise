import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

class AccountReturnWizardButton extends Component {
    static template = "account_reports.AccountReturnWizardButton";
    props = useProps({
        ...standardWidgetProps,
        btnClass: t.string().optional("btn btn-primary"),
        string: t.string().optional(""),
        call: t.string(),
    });

    orm = usePlugin(ORM);
    action = usePlugin(ActionPlugin);

    async onClick() {
        if (!this.props.call) {
            throw "Call props is missing";
        }

        const result = await this.orm.call(
            this.props.record.resModel,
            this.props.call,
            [this.props.record.resId]
        )
        this.props.record.model.load();

        if (result) {
            this.action.doAction(result);
        }
    }
}

export const accountReturnWizardButton = {
    component: AccountReturnWizardButton,
    extractProps: ({ attrs }) => ({
        btnClass: attrs.btn_class,
        string: attrs.string,
        call: attrs.call
    })
}

registry.category("view_widgets").add("account_return_wizard_button", accountReturnWizardButton)
