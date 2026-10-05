import { markup, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { usePlanningPopoverActions } from "@planning/views/planning_hooks";
import { MapRenderer } from "@web_map/map_view/map_renderer";
import { PlanningEmployeeAvatar } from "@planning/views/planning_gantt/planning_employee_avatar";
import { PlanningFieldServiceMapPopover } from "./planning_field_service_map_popover";

export class PlanningFieldServiceMapRenderer extends MapRenderer {
    static routingPopupTemplate = "planning_field_service.routingPopup";
    static components = {
        ...MapRenderer.components,
        Avatar: PlanningEmployeeAvatar,
        Popover: PlanningFieldServiceMapPopover,
    };

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.fieldServiceGeolocation = useService("field_service_geolocation");
        this.popoverActions = usePlanningPopoverActions();
        this.isPlanningManager = false;
        onWillStart(async () => {
            this.isPlanningManager = await user.hasGroup("planning.group_planning_manager");
        });
    }

    /**
     * @override
     */
    getRoutingPopupData(groupId, route) {
        const popupData = super.getRoutingPopupData(groupId, route);
        if (this.props.model.data.groupByKey !== "resource_ids") {
            return popupData;
        }
        const records = this.props.model.data.allRecordGroups[groupId].records;
        const resources = records.map((r) => r.resource_ids.find((res) => res.id == groupId));
        if (!resources.every(Boolean)) {
            return popupData;
        }
        return {
            ...popupData,
            resourceId: groupId,
            isResourceMaterial: resources[0].resource_type === "material",
            resourceColor: this.getGroupColor(groupId),
        };
    }

    /**
     * @override
     */
    getPopoverProps(markerInfo) {
        const popoverProps = super.getPopoverProps(markerInfo);
        const { record, ids } = markerInfo;
        if (!ids || ids.length !== 1) {
            // Start/unschedule/delete only make sense for a single shift: a marker
            // grouping several shifts at the same location keeps the default Edit/View button.
            return popoverProps;
        }
        if (record.can_edit && record.state === "2_published" && record.partner_id) {
            popoverProps.onStart = async () => {
                const context = {};
                if (record.user_ids.some((user_) => user_.id === user.userId)) {
                    this.fieldServiceGeolocation.startWatch();
                    context.geolocation = await this.fieldServiceGeolocation.getGeolocation();
                }
                await this.orm.call(this.model.metaData.resModel, "action_sign_in", [record.id], {
                    context,
                });
                this.model.load({});
                const message = _t("Shift started");
                this.notification.add(
                    markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
                    { type: "success" }
                );
            };
        }
        if (record.can_edit && record.state === "3_in_progress") {
            popoverProps.onComplete = async () => {
                await this.orm.call(this.model.metaData.resModel, "action_complete", [record.id]);
                this.model.load({});
                const message = _t("Completed");
                this.notification.add(
                    markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
                    { type: "success" }
                );
            };
        }
        if (this.isPlanningManager) {
            const args = {
                orm: this.orm,
                resModel: this.model.metaData.resModel,
                record,
                reload: () => this.model.load({}),
            };
            popoverProps.onUnschedule = this.popoverActions.makeOnUnschedule(args);
            popoverProps.onDelete = this.popoverActions.makeOnDelete(args);
        }
        if (record.partner_city && record.partner_country_id) {
            popoverProps.onNavigate = async () => {
                const action = await this.model.orm.call(
                    this.model.metaData.resModel,
                    "action_open_map_navigation",
                    [record.id]
                );
                if (action?.type === "ir.actions.act_url") {
                    this.actionService.doAction(action);
                }
            };
        }
        return popoverProps;
    }
}
