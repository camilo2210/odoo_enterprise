import { onWillStart, Portal, providePlugins, signal, usePlugin } from "@odoo/owl";
import { parseDateTime, serializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useDraggable } from "@web/core/utils/draggable";
import { parseXML } from "@web/core/utils/xml";

import { MapController } from "@web_map/map_view/map_controller";

import { MapTimelineCommunicationPlugin } from "./map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";
import { MapTimelineGanttController } from "./map_timeline_gantt_view/planning_field_service_map_timeline_gantt_controller";
import { planningFieldServiceMapTimelineGanttView } from "./map_timeline_gantt_view/planning_field_service_map_timeline_gantt_view";

export class PlanningFieldServiceMapTimelineController extends MapController {
    static template = "planning_field_service.MapTimelineView";
    static components = {
        ...MapController.components,
        MapTimelineGanttController,
        Portal,
    };

    resizeContainerRef = signal.ref();
    mapPaneRef = signal.ref();
    ganttContainerRef = signal.ref();

    setup() {
        providePlugins([MapTimelineCommunicationPlugin]);

        super.setup(...arguments);

        this.communication = usePlugin(MapTimelineCommunicationPlugin);
        this.communication.onNotify(() => {
            this.model.preserveMapPosition = true;
            this.model.load({});
        });

        onWillStart(async () => {
            const { views } = await this.env.services.view.loadViews({
                context: this.props.context,
                resModel: this.props.resModel,
                views: [[false, "gantt"]],
            });
            this.ganttArch = parseXML(views.gantt.arch);
        });

        let initialHeight = 0;
        let initialY = 0;
        useDraggable({
            ref: this.resizeContainerRef,
            elements: ".o_map_timeline_resize",
            cursor: "row-resize",
            onDragStart: ({ y }) => {
                initialY = y;
                initialHeight = this.mapPaneRef().offsetHeight;
            },
            onDrag: ({ y }) => {
                this.mapPaneRef().style.height = `${initialHeight + y - initialY}px`;
            },
        });
    }

    get activeDateFilterFocusDate() {
        const { searchItems, query } = this.env.searchModel;
        const filterItem = Object.values(searchItems).find(
            (item) => item.type === "relativeFilter" && item.fieldName === "start_datetime"
        );
        const activeItem = filterItem && query.find((q) => q.searchItemId === filterItem.id);
        if (!activeItem || activeItem.optionId !== "today") {
            return false;
        }
        const offset = activeItem.offset || 0;
        return parseDateTime(`today ${offset < 0 ? "-" : "+"}${Math.abs(offset)}d`);
    }

    get ganttProps() {
        const context = {
            ...this.props.context,
            default_scale: "day",
            initialDate: serializeDateTime(this.activeDateFilterFocusDate),
            // So the gantt's "Shifts to Schedule" side panel lists records in
            // the same order as the map's own pin-list/pin, instead of
            // falling back to planning.slot's own default order.
            shiftsToScheduleOrder: this.model.metaData.defaultOrder,
        };
        return planningFieldServiceMapTimelineGanttView.props(
            { ...this.props, arch: this.ganttArch, context },
            planningFieldServiceMapTimelineGanttView,
            this.env.config
        );
    }

    createRecord() {
        const focusDate = this.activeDateFilterFocusDate;
        if (!focusDate) {
            return this.props.createRecord();
        }
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: this.env.config.getDisplayName() || _t("Untitled"),
                res_model: this.props.resModel,
                views: this._getActionViews("form"),
                res_id: false,
                context: {
                    ...this.props.context,
                    default_start_datetime: serializeDateTime(focusDate.startOf("day")),
                    default_end_datetime: serializeDateTime(focusDate.endOf("day")),
                },
            },
            {
                onClose: () => this.model.load({}),
            }
        );
    }
}
