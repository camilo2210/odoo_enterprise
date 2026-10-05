/*global L*/

import { proxy, usePlugin } from "@odoo/owl";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { renderToString } from "@web/core/utils/render";
import { MapPinListPopover } from "@web_map/map_view/map_renderer";
import { PlanningFieldServiceMapRenderer } from "@planning_field_service/views/planning_field_service_map/planning_field_service_map_renderer";

const { DateTime } = luxon;

const PIN_ICON_W = 25;
const PIN_ICON_H = 25;

export class PlanningFieldServiceLiveMapPinListPopover extends MapPinListPopover {
    static subTemplates = {
        ...MapPinListPopover.subTemplates,
        PinListContainer: "planning_field_service.LiveMapRenderer.PinListContainer",
    };
}

export class PlanningFieldServiceLiveMapRenderer extends PlanningFieldServiceMapRenderer {
    static template = "planning_field_service.LiveMapRenderer";
    static subTemplates = {
        ...PlanningFieldServiceMapRenderer.subTemplates,
        PinListContainer: "planning_field_service.LiveMapRenderer.PinListContainer",
    };
    static Popover = PlanningFieldServiceLiveMapPinListPopover;

    debugMode = usePlugin(DebugModePlugin);

    /**
     * @override
     */
    setup() {
        super.setup(...arguments);
        this.isDemoDataActive = proxy({ value: false });
        useService("lazy_session").getValue("is_demo", (v) => (this.isDemoDataActive.value = !!v));
    }

    async createUserMarkerPopup(popupData, isOnClick) {
        const lastUpdate = deserializeDateTime(popupData.live_location_last_update);
        popupData.relative_time =
            DateTime.now().diff(lastUpdate, "minutes").minutes < 1
                ? _t("Just now")
                : lastUpdate.toRelative();

        const popupHtml = renderToString("planning_field_service.userMarkerPopup", popupData);
        const popup = L.popup({
            offset: [0, -PIN_ICON_H],
            closeButton: isOnClick,
            className: "field-service-user-popup",
            maxWidth: 395,
        })
            .setLatLng([popupData.live_latitude, popupData.live_longitude])
            .setContent(popupHtml)
            .openOn(this.leafletMap);
        return popup;
    }

    get resourcesToDiplay() {
        let resourcesToDisplay = [];
        if (this.props.model.data.isGrouped) {
            resourcesToDisplay = Object.entries(this.props.model.data.recordGroups)
                .filter(([id]) => !this.props.model.closedGroupIds().has(id))
                .flatMap(([, value]) => value.records)
                .flatMap((r) => r.resource_ids.map(({ id }) => id));
        } else {
            resourcesToDisplay = this.props.model.data.records.flatMap((r) =>
                r.resource_ids.map(({ id }) => id)
            );
        }
        return new Set(resourcesToDisplay);
    }

    addMarkers() {
        super.addMarkers();
        if (!this.props.model.data.locatedResources.length) {
            return;
        }
        const resourcesToDiplay = this.resourcesToDiplay;
        const records = this.props.model.data.locatedResources.filter(({ id }) =>
            resourcesToDiplay.has(id)
        );
        for (const record of records) {
            const { id, live_latitude, live_longitude } = record;
            const iconInfo = {
                className: "",
                html: renderToString("planning_field_service.userMarker", { id }),
                iconSize: [PIN_ICON_W, PIN_ICON_H],
                iconAnchor: [Math.round(PIN_ICON_W / 2), PIN_ICON_H],
            };
            const marker = L.marker([live_latitude, live_longitude], {
                icon: L.divIcon(iconInfo),
            });
            marker.addTo(this.leafletMap);
            if (this.uiService.isSmall) {
                marker.on("click", () => {
                    this.createUserMarkerPopup(record, true);
                });
            } else {
                marker.on("mouseover", () => {
                    this.createUserMarkerPopup(record, false);
                });
                marker.on("mouseout", () => {
                    this.leafletMap.closePopup();
                });
            }
            this.markers.push(marker);
        }
    }

    isResourceLocated(resourceId) {
        return (
            this.props.model.data.groupByKey === "resource_ids" &&
            !this.props.model.closedGroupIds().has(resourceId) &&
            this.props.model.data.locatedResources.find((r) => r.id == resourceId)
        );
    }

    focusOnUserPin(groupId) {
        let resource;
        if (
            this.props.model.data.groupByKey !== "resource_ids" ||
            !(resource = this.props.model.data.locatedResources.find((r) => r.id == groupId))
        ) {
            return;
        }
        // Hide routes during animation and display them back
        this.polylines.forEach((p) => p.remove());
        this.leafletMap.flyTo(L.latLng(resource.live_latitude, resource.live_longitude), 10, {
            animate: true,
            duration: 2,
        });
        this.leafletMap.once("moveend", () => {
            this.polylines.forEach((p) => p.addTo(this.leafletMap));
        });
    }

    get userLocationTooltip() {
        return _t("View location");
    }

    async generateSampleData() {
        await this.orm.call("planning.slot", "action_generate_live_map_demo_data");
        await this.model.load({});
    }
}
