import { onMounted, onWillUnmount, usePlugin } from "@odoo/owl";

import { PlanningFieldServiceMapRenderer } from "@planning_field_service/views/planning_field_service_map/planning_field_service_map_renderer";

import { MapTimelineCommunicationPlugin } from "./map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";

const colorlistColorCache = new Map();
let colorlistProbeEl;

function getColorlistColor(index) {
    if (!colorlistColorCache.has(index)) {
        if (!colorlistProbeEl) {
            colorlistProbeEl = document.createElement("div");
            colorlistProbeEl.style.display = "none";
            document.body.appendChild(colorlistProbeEl);
        }
        colorlistProbeEl.className = `o_colorlist_toggler o_colorlist_item_color_${index}`;
        colorlistColorCache.set(index, getComputedStyle(colorlistProbeEl).backgroundColor);
    }
    return colorlistColorCache.get(index);
}

export class PlanningFieldServiceMapTimelineRenderer extends PlanningFieldServiceMapRenderer {
    static markerTemplate = "planning_field_service.marker";
    static subTemplates = {
        ...PlanningFieldServiceMapRenderer.subTemplates,
        PinListContainer: "planning_field_service.MapTimelineMapRenderer.PinListContainer",
    };

    communication = usePlugin(MapTimelineCommunicationPlugin);

    setup() {
        super.setup(...arguments);
        this.communication.onHighlight(({ recordIds, on }) => {
            for (const id of recordIds) {
                super.onPinListHover({ id }, on);
            }
            super.onMarkerHover(recordIds, on);
        });

        // Leaflet only re-layouts on window resize: notify it when the pane
        // is resized with the handle between the map and the gantt.
        const resizeObserver = new ResizeObserver(() => this.leafletMap?.invalidateSize());
        onMounted(() => resizeObserver.observe(this.mapContainerRef()));
        onWillUnmount(() => resizeObserver.disconnect());
    }

    /**
     * @override
     */
    getGroupColor(groupId) {
        if (this.props.model.data.groupByKey !== "resource_ids") {
            return super.getGroupColor(groupId);
        }
        const record = this.props.model.data.allRecordGroups[groupId].records[0];
        const resource = record.resource_ids.find((r) => r.id == groupId);
        if (!resource || resource.resource_type !== "material") {
            return super.getGroupColor(groupId);
        }
        return getColorlistColor(resource.color);
    }

    /**
     * @override
     */
    onPinListHover(record, on) {
        super.onPinListHover(record, on);
        this.communication.highlight([record.id], on);
    }

    /**
     * @override
     */
    onMarkerHover(recordIds, on) {
        super.onMarkerHover(recordIds, on);
        this.communication.highlight(recordIds, on);
    }

    onPinListHeaderHover(groupId, on) {
        for (const record of this.props.model.data.recordGroups[groupId].records) {
            this.onPinListHover(record, on);
            const marker = this.markerByRecordId.get(record.id)?.getElement?.();
            if (marker) {
                marker.classList.toggle("o_map_marker_group_hover", on);
            }
        }
        const polyline = this.polylineByGroupId.get(groupId);
        polyline?.setStyle({ opacity: on ? 0.8 : 0.5, weight: on ? 7 : 5 });
    }
}
