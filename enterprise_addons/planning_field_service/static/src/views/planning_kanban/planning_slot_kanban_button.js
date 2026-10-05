import { Component, markup, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class PlanningSlotKanbanButton extends Component {
    static template = "planning_field_service.PlanningSlotAction";

    props = useProps(standardWidgetProps);

    setup() {
        this.orm = useService("orm");
        this.user = user;
        this.fieldServiceGeolocation = useService("field_service_geolocation");
        this.notification = useService("notification");
    }

    get isKanbanView() {
        return this.env.config?.viewType === "kanban";
    }

    get isAssignedToCurrentUser() {
        return this.props.record.data.user_ids.records.some(
            (record) => record.resId === this.user.userId
        );
    }

    get displayButtons() {
        return this.props.record.data.can_edit && this.props.record.data.partner_id;
    }

    async getAdditionalContext() {
        const context = {};
        if (this.props.record.data.user_ids.resIds.includes(this.user.userId)) {
            this.fieldServiceGeolocation.startWatch();
            context.geolocation = await this.fieldServiceGeolocation.getGeolocation();
        }
        return context;
    }

    async onSignIn() {
        const context = await this.getAdditionalContext();
        await this.orm.call("planning.slot", "action_sign_in", [this.props.record.resId], {
            context,
        });
        this.props.record.load();
        const message = _t("Shift started");
        this.notification.add(
            markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
            { type: "success" }
        );
    }

    async onComplete() {
        const context = await this.getAdditionalContext();
        await this.orm.call("planning.slot", "action_complete", [this.props.record.resId], {
            context,
        });
        this.props.record.load();
        const message = _t("Completed");
        this.notification.add(
            markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
            { type: "success" }
        );
    }
}

registry
    .category("view_widgets")
    .add("planning_slot_kanban_button", { component: PlanningSlotKanbanButton });
