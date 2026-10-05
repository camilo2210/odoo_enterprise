import { signal, usePlugin } from "@odoo/owl";

import { GanttSidePanel } from "@web_gantt/gantt_side_panel";

import { MapTimelineCommunicationPlugin } from "../map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";

export class MapTimelineGanttSidePanel extends GanttSidePanel {
    static panelTemplate = "planning_field_service.MapTimelineGanttSidePanel.Panel";

    communication = usePlugin(MapTimelineCommunicationPlugin);
    highlightedRecordIds = signal.Set();

    setup() {
        super.setup(...arguments);
        this.communication.onHighlight(({ recordIds, on }) => {
            const highlightedRecordIds = this.highlightedRecordIds();
            for (const id of recordIds) {
                if (on) {
                    highlightedRecordIds.add(id);
                } else {
                    highlightedRecordIds.delete(id);
                }
            }
        });
    }

    /**
     * @param {Number} recordId
     * @param {Boolean} on
     */
    onEventHover(recordId, on) {
        this.communication.highlight([recordId], on);
    }
}
