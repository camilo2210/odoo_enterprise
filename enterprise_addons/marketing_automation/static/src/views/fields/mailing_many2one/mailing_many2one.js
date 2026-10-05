import { Component, computed, usePlugin, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import {
    buildM2OFieldDescription,
    many2OneFieldProps,
} from "@web/views/fields/many2one/many2one_field";
import { MarketingAutomationAddStepPlugin } from "@marketing_automation/plugins/add_step_plugin/add_step_plugin";

class MailingMany2OneField extends Component {
    static template = "marketing_automation.MailingMany2OneField";
    static components = { Many2One };
    props = useProps({ ...many2OneFieldProps });

    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.showDesignButton = computed(
            () =>
                !this.props.record.data.mass_mailing_id &&
                this.props.record.data.campaign_mass_mailing_count == 0
        );
        this.addStepPlugin = usePlugin(MarketingAutomationAddStepPlugin);
    }

    get m2oProps() {
        return {
            ...computeM2OProps(this.props),
            openRecordAction: () => this.openRecordInAction(),
            createAction: (params) => this.createAction(params),
        };
    }

    openAction(resId, context) {
        this.action.doAction("marketing_automation.mailing_mailing_action_view_form", {
            props: { resId },
            additionalContext: context,
        });
    }

    async createAction({ context }) {
        const id = await this.addStepPlugin.execute(this.props.record);
        if (!id) {
            return;
        }
        const actionContext = {
            ...context,
            ...this.props.context,
            default_marketing_activity_ids: [id],
        };
        this.openAction(false, actionContext);
    }

    async openRecordInAction() {
        const id = await this.addStepPlugin.execute(this.props.record);
        if (!id) {
            return;
        }
        const { value, openActionContext } = this.m2oProps;
        this.openAction(value?.id || false, openActionContext());
    }
}

registry.category("fields").add("mailing_many2one", {
    ...buildM2OFieldDescription(MailingMany2OneField),
});
