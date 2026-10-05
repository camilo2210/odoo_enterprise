import { PlanningCalendarCommonPopover } from "@planning/views/planning_calendar/common/planning_calendar_common_popover";

import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { markup } from "@odoo/owl";

patch(PlanningCalendarCommonPopover.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
        this.fieldServiceGeolocation = useService("field_service_geolocation");
        this.notification = useService("notification");
    },

    get readonly() {
        return !this.props.record.rawRecord.can_edit;
    },

    get canStart() {
        return (
            this.props.record.rawRecord.can_edit &&
            this.props.record.rawRecord.state === "2_published" &&
            this.props.record.rawRecord.partner_id
        );
    },

    get canComplete() {
        return (
            this.props.record.rawRecord.can_edit &&
            this.props.record.rawRecord.state === "3_in_progress"
        );
    },

    get displayMapNavigationButton() {
        const { partner_city: partnerCity, partner_country_id: partnerCountry } =
            this.props.record.rawRecord;
        return Boolean(partnerCity && partnerCountry);
    },

    async onStart() {
        const context = {};
        if (this.props.record.rawRecord.user_ids.includes(user.userId)) {
            this.fieldServiceGeolocation.startWatch();
            context.geolocation = await this.fieldServiceGeolocation.getGeolocation();
        }
        await this.orm.call(
            this.props.model.meta.resModel,
            "action_sign_in",
            [this.props.record.rawRecord.id],
            {
                context,
            }
        );
        await this.props.model.load();
        const message = _t("Shift started");
        this.notification.add(
            markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
            { type: "success" }
        );
    },

    async onOpenMapNavigation() {
        const action = await this.orm.call(
            this.props.model.meta.resModel,
            "action_open_map_navigation",
            [this.props.record.rawRecord.id]
        );
        if (action?.type === "ir.actions.act_url") {
            this.action.doAction(action);
        }
    },

    async onComplete() {
        await this.orm.call(this.props.model.meta.resModel, "action_complete", [
            this.props.record.rawRecord.id,
        ]);
        await this.props.model.load();
        const message = _t("Completed");
        this.notification.add(
            markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
            { type: "success" }
        );
    },
});
