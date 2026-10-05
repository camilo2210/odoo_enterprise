import { usePlugin } from "@odoo/owl";

import { PlanningGanttRenderer } from "@planning/views/planning_gantt/planning_gantt_renderer";

import { MapTimelineCommunicationPlugin } from "../map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";
import { MapTimelineGanttSidePanel } from "./planning_field_service_map_timeline_gantt_side_panel";

export class MapTimelineGanttRenderer extends PlanningGanttRenderer {
    static template = "planning_field_service.MapTimelineGanttRenderer";
    static headerTemplate = "planning_field_service.MapTimelineGanttRenderer.Header";
    static components = {
        ...PlanningGanttRenderer.components,
        GanttSidePanel: MapTimelineGanttSidePanel,
    };

    communication = usePlugin(MapTimelineCommunicationPlugin);

    setup() {
        super.setup(...arguments);
        this.communication.onHighlight(({ recordIds, on }) => {
            for (const [pillId, pill] of Object.entries(this.pills)) {
                if (pill.record && recordIds.includes(pill.record.id)) {
                    this.highlightPill(pillId, on);
                }
            }
        });
    }

    /**
     * @override
     */
    processRow(row, pills, processAsGroup) {
        if (this.communication.isFolded(row.resId)) {
            return { rows: [], pillsToProcess: pills };
        }
        return super.processRow(row, pills, processAsGroup);
    }

    /**
     * Folding every row (e.g. folding the only row left, "Open Shifts") leaves `this.rows` empty,
     * which is not expected as the Gantt assumes there is always one row to display.
     * @override
     */
    computeVisibleRows() {
        if (!this.rows.length) {
            this.rowsToRender = new Set();
            return;
        }
        super.computeVisibleRows();
    }

    /**
     * @override
     */
    get hasSidePanel() {
        return super.hasSidePanel && !this.communication.shiftsToScheduleFolded;
    }

    /**
     * @override
     */
    computeDerivedParamsFromHover() {
        super.computeDerivedParamsFromHover(...arguments);
        if (this.isDragging) {
            return;
        }
        const hoveredPillId = this.hovered.pill?.dataset.pillId;
        const recordId = (hoveredPillId && this.pills[hoveredPillId]?.record?.id) || null;
        if (recordId !== this.highlightedRecordId) {
            if (this.highlightedRecordId) {
                this.communication.highlight([this.highlightedRecordId], false);
            }
            if (recordId) {
                this.communication.highlight([recordId], true);
            }
            this.highlightedRecordId = recordId;
        }
    }
}
