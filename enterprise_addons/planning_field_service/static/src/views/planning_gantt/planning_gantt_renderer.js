import { _t } from "@web/core/l10n/translation";
import { pick } from "@web/core/utils/objects";
import { patch } from "@web/core/utils/patch";
import { usePopover } from "@web/core/popover/popover_hook";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { formatDateTime, formatFloat, formatFloatTime } from "@web/views/fields/formatters";

import { PlanningGanttRenderer } from "@planning/views/planning_gantt/planning_gantt_renderer";

import { Component, markup, t, useProps } from "@odoo/owl";

class PlanningGanttBufferPopover extends Component {
    static template = "planning_field_service.PlanningGanttBufferPopover";

    props = useProps({
        departTime: t.string(),
        travelTime: t.string(),
        travelDistance: t.string(),
    });
}

patch(PlanningGanttRenderer, {
    pillTemplate: "planning_field_service.GanttRenderer.Pill",
});

patch(PlanningGanttRenderer.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.fieldServiceGeolocation = useService("field_service_geolocation");
        this.bufferPopover = usePopover(PlanningGanttBufferPopover, { position: "top-start" });
    },
    /**
     * @override
     */
    get showBufferTimes() {
        return (
            super.showBufferTimes && this.props.model.metaData.groupedBy.includes("resource_ids")
        );
    },
    /**
     * @override
     */
    computeDerivedParams() {
        super.computeDerivedParams();
        // Visually remove the buffer end if there is a subsequent pill (i.e., shift in our case)
        for (const [, pills] of Object.entries(this.rowPills)) {
            pills.slice(0, -1).forEach((pill) => {
                if (pill.buffer) {
                    pill.buffer = { column: [pill.buffer.column[0], pill.grid.column[1]] };
                }
            });
        }
    },

    async getAdditionalContext(record) {
        const context = {};
        if (record.user_ids.includes(user.userId)) {
            this.fieldServiceGeolocation.startWatch();
            context.geolocation = await this.fieldServiceGeolocation.getGeolocation();
        }
        return context;
    },

    /**
     * @override
     */
    getPopoverProps(pill) {
        const popoverProps = super.getPopoverProps(pill);
        const { record } = pill;
        if (record.can_edit && record.partner_id) {
            if (record.state === "2_published") {
                popoverProps.onStart = async () => {
                    const context = await this.getAdditionalContext(record);
                    await this.model.orm.call(
                        this.model.metaData.resModel,
                        "action_sign_in",
                        [record.id],
                        {
                            context,
                        }
                    );
                    const message = _t("Shift started");
                    this.notification.add(
                        markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
                        { type: "success" }
                    );
                    this.model.fetchData();
                };
            } else if (record.state === "3_in_progress") {
                popoverProps.onComplete = async () => {
                    const context = await this.getAdditionalContext(record);
                    await this.model.orm.call(
                        this.model.metaData.resModel,
                        "action_complete",
                        [record.id],
                        {
                            context,
                        }
                    );
                    const message = _t("Completed");
                    this.notification.add(
                        markup`<i class="oi oi-fw" data-icon="check"></i><span class="ms-1">${message}</span>`,
                        { type: "success" }
                    );
                    this.model.fetchData();
                };
            }
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
        if (this.props.context.my_planning_action) {
            popoverProps.openRecord = () => {
                const { resModel } = this.props.model.metaData;
                const action = {
                    type: "ir.actions.act_window",
                    res_model: resModel,
                    views: [[false, "form"]],
                    target: "current",
                    context: this.props.context,
                };
                if (record.id) {
                    action.res_id = record.id;
                }
                this.actionService.doAction(action);
            };
        }
        return popoverProps;
    },

    /**
     * @override
     */
    onCellClicked(rowId, column, row) {
        if (!this.isPlanningManager) {
            return;
        }
        super.onCellClicked(rowId, column, row);
    },

    /**
     * @override
     */
    getPill(record) {
        const pill = super.getPill(record);
        if (!record.can_edit) {
            pill.disableDrag = true;
            pill.disableStartResize = true;
            pill.disableStopResize = true;
        }
        return pill;
    },

    /**
     * @override
     */
    getUndoAfterDragRecordData(record) {
        return {
            ...super.getUndoAfterDragRecordData(...arguments),
            ...pick(
                record,
                this.model.metaData.bufferStartField,
                this.model.metaData.bufferStopField,
                "travel_distance_in",
                "travel_distance_out",
                "travel_times_up_to_date"
            ),
        };
    },
    onBufferMouseEnter(ev, pill) {
        const record = pill.record;
        this.bufferPopover.open(ev.currentTarget, {
            departTime: formatDateTime(
                record[this.model.metaData.dateStartField].plus({
                    hours: -record[this.model.metaData.bufferStartField],
                }),
                { showDate: false }
            ),
            travelTime: formatFloatTime(record[this.model.metaData.bufferStartField]),
            travelDistance:
                record.travel_distance_in < 1
                    ? `${Math.round(record.travel_distance_in * 1000)} m`
                    : `${formatFloat(record.travel_distance_in, { digits: [69, 0] })} km`,
        });
    },
    onBufferMouseLeave() {
        this.bufferPopover.close();
    },
});
