/*global L*/

import { render } from "@web/owl2/utils";
import { _t } from "@web/core/l10n/translation";
import { renderToString } from "@web/core/utils/render";
import { isMacOS } from "@web/core/browser/feature_detection";
import { formatFloatTime } from "@web/views/fields/formatters";
import { useBus, useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { usePopover } from "@web/core/popover/popover_hook";
import { MapPopover } from "@web_map/map_view/map_popover";

import {
    Component,
    onMounted,
    onPatched,
    onWillUnmount,
    proxy,
    signal,
    t,
    useListener,
    useProps,
} from "@odoo/owl";

const apiTilesRouteWithToken =
    "https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}";
const apiTilesRouteWithoutToken = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png";

const colors = [
    "#007E82",
    "#F06050",
    "#6CC1ED",
    "#F7CD1F",
    "#814968",
    "#30C381",
    "#475577",
    "#F4A460",
    "#EB7E7F",
    "#2C8397",
];

export const PIN_ICON_W = 27;
export const PIN_ICON_H = 41;

export const PIN_LIST_INITIAL_WIDTH = 280;
export const PIN_LIST_MIN_WIDTH = 200;

/**
 * @typedef Location
 * @property {string} address
 * @property {number} latitude
 * @property {number} longitude
 */

const mapTileAttribution = `
    © <a href="https://www.mapbox.com/about/maps/">Mapbox</a>
    © <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>
    <strong>
        <a href="https://www.mapbox.com/map-feedback/" target="_blank">
            Improve this map
        </a>
    </strong>`;

export class MapPinListPopover extends Component {
    static template = "web_map.PinListPopover";
    static subTemplates = {
        PinListContainer: "web_map.MapRenderer.PinListContainer",
        PinList: "web_map.MapRenderer.PinList",
        PinListItems: "web_map.MapRenderer.PinListItems",
    };
    props = useProps({
        model: t.object(),
        renderer: t.object(),
        close: t.function(),
    });

    // The shared "PinListContainer" sub-template binds t-ref="this.pinListContainerRef";
    // define the signal here too so it resolves when rendered by this popover.
    pinListContainerRef = signal.ref();

    setup() {
        this.uiService = useService("ui");
        this.state = proxy(this.props.renderer.state);
        useBus(this.props.model.bus, "update", () => {
            render(this);
        });
    }
    get subTemplates() {
        return this.constructor.subTemplates;
    }
}

export class MapRenderer extends Component {
    static template = "web_map.MapRenderer";
    static markerTemplate = "web_map.marker";
    static markerPopupTemplate = "web_map.markerPopup";
    static routingPopupTemplate = "web_map.routingPopup";
    props = useProps({
        model: t.object(),
        onMarkerClick: t.function(),
    });
    static components = {
        AutoComplete,
        Popover: MapPopover,
    };
    static subTemplates = {
        AddressAutocomplete: "web_map.MapRenderer.AddressAutocomplete",
        PinListContainer: "web_map.MapRenderer.PinListContainer",
        PinList: "web_map.MapRenderer.PinList",
        PinListItems: "web_map.MapRenderer.PinListItems",
        FetchingCoordinates: "web_map.MapRenderer.FetchingCoordinates",
        NoMapToken: "web_map.MapRenderer.NoMapToken",
    };
    static Popover = MapPinListPopover;

    mapContainerRef = signal.ref();
    pinListContainerRef = signal.ref();
    addressAutocompleteRef = signal.ref();

    get subTemplates() {
        return this.constructor.subTemplates;
    }

    setup() {
        this.leafletMap = null;
        this.markers = [];
        this.markerByRecordId = new Map();
        this.polylines = [];
        this.polylineByGroupId = new Map();
        this.userPositionMarker = null;
        this.recordToOpen = null;
        this.state = proxy({
            expandedPinList: false,
            hasInput: false,
        });
        this.pinListWidth = PIN_LIST_INITIAL_WIDTH;
        this.isResizingPinList = false;
        this.pinListResizeState = null;
        useListener(window, "resize", () => this.onWindowResizePinList());
        this.nextId = 1;
        this.orm = useService("orm");
        this.http = useService("http");
        this.uiService = useService("ui");
        this.pinListPopover = usePopover(this.constructor.Popover, {
            useBottomSheet: true,
            onClose: () => (this.state.expandedPinList = false),
        });
        this.forceFullUpdate = true;
        this.debouncedInvalidateMapSize = useDebounced(
            () => this.leafletMap?.invalidateSize(),
            100
        );

        this.model = this.props.model;
        this.popover = usePopover(this.constructor.components.Popover, {
            onClose: () => this.onCloseCurrentPopover?.(),
        });

        onMounted(() => {
            this.leafletMap = L.map(this.mapContainerRef(), {
                maxBounds: [L.latLng(180, -180), L.latLng(-180, 180)],
            });
            this.leafletMap.attributionControl.setPrefix(
                '<a href="https://leafletjs.com" title="A JavaScript library for interactive maps">Leaflet</a>'
            );
            L.tileLayer(this.apiTilesRoute, {
                attribution: mapTileAttribution,
                tileSize: 512,
                zoomOffset: -1,
                minZoom: 2,
                maxZoom: 19,
                id: "mapbox/streets-v11",
                accessToken: this.props.model.geolocation.mapBoxToken,
            }).addTo(this.leafletMap);
            this.updateMap();
        });
        onPatched(() => {
            this.updateMap();
            if (this.recordToOpen) {
                this.centerAndOpenPinOnPatched(this.recordToOpen);
                this.recordToOpen = null;
            }
        });

        onWillUnmount(this.onWillUnmount);
    }
    /**
     * Remove map and the listeners on its markers and routes.
     */
    onWillUnmount() {
        this.clearResizeListeners?.();
        this.removeMarkers();
        this.removeRoutes();
        if (this.leafletMap) {
            this.leafletMap.remove();
            this.leafletMap = null;
        }
    }

    getPopoverProps(markerInfo) {
        const resIds = markerInfo.ids || [markerInfo.record.id];
        return {
            model: this.model,
            resIds,
            record: markerInfo.record,
            openRecord: (event) => this.onClickOpen(event, resIds),
            reloadOnClose: () => {
                this.onCloseCurrentPopover = () => {
                    delete this.onCloseCurrentPopover;
                    this.model.load({});
                };
            },
        };
    }

    /**
     * Return the route to the tiles api with or without access token.
     *
     * @returns {string}
     */
    get apiTilesRoute() {
        return this.props.model.geolocation.useMapBoxAPI
            ? apiTilesRouteWithToken
            : apiTilesRouteWithoutToken;
    }

    get addressAutocompleteSources() {
        return [
            {
                options: async (request) => {
                    if (request.length >= 3) {
                        const suggestions =
                            await this.props.model.geolocation.searchCoordinatesFromAddress(
                                request
                            );
                        return suggestions.map((location) => ({
                            cssClass: "o_map_address_result",
                            label: location.address,
                            onSelect: () => this.updateUserPosition(location),
                        }));
                    } else if (request.length === 0) {
                        this.updateUserPosition({});
                    }
                    return [{ cssClass: "fst-italic", label: _t("Start typing 3 characters") }];
                },
                optionSlot: "option",
                placeholder: _t("Searching for addresses..."),
            },
        ];
    }

    get locationTooltip() {
        return _t("Use your location");
    }

    get currentAddress() {
        return this.isUserLocated
            ? _t("Your location")
            : this.props.model.data.userPosition.address;
    }

    get isUserLocated() {
        const { address, latitude, longitude } = this.props.model.data.userPosition;
        return !address && latitude && longitude;
    }

    /**
     * If there's located records, adds the corresponding marker on the map.
     * Binds events to the created markers.
     */
    addMarkers() {
        this.removeMarkers();

        const markersInfo = {};
        let records = this.props.model.data.records;
        if (this.props.model.data.isGrouped) {
            records = Object.entries(this.props.model.data.recordGroups)
                .filter(([key]) => !this.props.model.closedGroupIds().has(key))
                .flatMap(([groupId, value]) => value.records.map((elem) => ({ ...elem, groupId })));
        }

        const pinInSamePlace = {};
        for (const record of records) {
            const partner = record.partner;
            if (partner && partner.partner_latitude && partner.partner_longitude) {
                const lat_long = `${partner.partner_latitude}-${partner.partner_longitude}`;
                const group = this.props.model.data.isGrouped ? `-${record.groupId}` : "";
                const key = `${lat_long}${group}`;
                if (key in markersInfo) {
                    markersInfo[key].record = record;
                    markersInfo[key].relatedRecords.push(record);
                    markersInfo[key].ids.push(record.id);
                } else {
                    pinInSamePlace[lat_long] = ++pinInSamePlace[lat_long] || 0;
                    markersInfo[key] = {
                        key,
                        record: record,
                        ids: [record.id],
                        pinInSamePlace: pinInSamePlace[lat_long],
                        relatedRecords: [],
                    };
                }
            }
        }

        for (const markerInfo of Object.values(markersInfo)) {
            const params = {
                color: colors[0],
                count: markerInfo.ids.length,
                isMulti: markerInfo.ids.length > 1,
                number: this.props.model.data.records.indexOf(markerInfo.record) + 1,
            };
            if (this.props.model.data.isGrouped) {
                const groupId = markerInfo.record.groupId;
                params.color = this.getGroupColor(groupId);
                params.number =
                    this.props.model.data.recordGroups[groupId].records.findIndex(
                        (record) => record.id === markerInfo.record.id
                    ) + 1;
            }

            // Icon creation
            const iconInfo = {
                className: "", // Prevent default
                html: renderToString(this.constructor.markerTemplate, params),
                iconSize: [PIN_ICON_W, PIN_ICON_H],
                iconAnchor: [Math.round(PIN_ICON_W / 2), PIN_ICON_H],
            };

            const offset = markerInfo.pinInSamePlace * 0.000025;
            // Attach marker with icon and popup
            const marker = L.marker(
                [
                    markerInfo.record.partner.partner_latitude + offset,
                    markerInfo.record.partner.partner_longitude - offset,
                ],
                { icon: L.divIcon(iconInfo) }
            );
            marker.addTo(this.leafletMap);
            marker.on("click", ({ originalEvent }) => {
                this.createMarkerPopup(originalEvent.target, markerInfo, offset);
            });
            marker.on("mouseover", () => {
                this.onMarkerHover(markerInfo.ids, true);
            });
            marker.on("mouseout", () => {
                this.onMarkerHover(markerInfo.ids, false);
            });
            this.markers.push(marker);
            for (const id of markerInfo.ids) {
                this.markerByRecordId.set(id, marker);
            }
        }
        const { latitude, longitude } = this.props.model.data.userPosition;
        if (latitude && longitude) {
            const params = {
                color: "#D6145F",
                count: 1,
                isMulti: 0,
                number: 0,
            };
            // Icon creation
            const iconInfo = {
                className: "", // Prevent default
                html: renderToString(this.constructor.markerTemplate, params),
                iconSize: [PIN_ICON_W, PIN_ICON_H],
                iconAnchor: [Math.round(PIN_ICON_W / 2), PIN_ICON_H],
            };
            const marker = L.marker([latitude, longitude], { icon: L.divIcon(iconInfo) });
            this.userPositionMarker = marker;
            marker.on("mouseover", () =>
                this.addressAutocompleteRef()?.classList.add("o_map_address_hover")
            );
            marker.on("mouseout", () =>
                this.addressAutocompleteRef()?.classList.remove("o_map_address_hover")
            );
            marker.on("click", () => {
                const { address } = this.props.model.data.userPosition;
                const url = address
                    ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(
                          address
                      )}`
                    : null;
                const popupHtml = renderToString(this.constructor.markerPopupTemplate, {
                    data: [{ id: 0, string: _t("Address"), value: this.currentAddress }],
                    hasFormView: false,
                    url,
                });
                L.popup({ offset: [0, -PIN_ICON_H] })
                    .setLatLng([latitude, longitude])
                    .setContent(popupHtml)
                    .openOn(this.leafletMap);
            });
            marker.addTo(this.leafletMap);
            this.markers.push(marker);
        }
    }
    onPinListHover(record, on) {
        const marker = this.markerByRecordId.get(record.id)?.getElement?.();
        if (marker) {
            marker.classList.toggle("o_map_marker_hover", on);
        }
    }
    onMarkerHover(recordIds, on) {
        const taskList = this.pinListContainerRef();
        if (taskList) {
            for (const id of recordIds) {
                const task = taskList.querySelector(`li[data-id="${id}"]`);
                if (task) {
                    task.classList.toggle("o_map_pin_hover", on);
                }
            }
        }
    }
    /**
     * Get the data to display in the popup
     *
     * @param {Number} groupId
     * @param {Object} route
     */
    getRoutingPopupData(groupId, route) {
        return {
            distance: Math.round(route.distance / 100) / 10,
            duration: formatFloatTime(route.duration / 60, {
                unit: "minutes",
                showSeconds: false,
            }),
        };
    }
    /**
     * If there are computed routes, create polylines and add them to the map.
     */
    addRoutes() {
        this.removeRoutes();
        if (
            !this.props.model.geolocation.useMapBoxAPI ||
            !Object.keys(this.props.model.data.routes).length
        ) {
            return;
        }
        for (const [groupId, route] of Object.entries(this.props.model.data.routes)) {
            if (route === null) {
                continue;
            }

            const latLngs = route.legs
                .flatMap((leg) => leg.steps)
                .flatMap((step) => step.geometry.coordinates)
                .map((coord) => L.latLng(coord[1], coord[0]));

            const polyline = L.polyline(latLngs, {
                color: this.getGroupColor(groupId) ?? "#007E82", // Fallback used when ungrouped
                weight: 5,
                interactive: false, // to remove cursor pointer style
                opacity: 0.5,
            }).addTo(this.leafletMap);

            const popupData = this.getRoutingPopupData(groupId, route);
            const tooltip = L.tooltip({
                opacity: 1,
                content: renderToString(this.constructor.routingPopupTemplate, popupData),
                permanent: true, // Always show, as onhover doesn't work with mobile
            });
            polyline.bindTooltip(tooltip);
            this.polylines.push(polyline);
            this.polylineByGroupId.set(groupId, polyline);
        }
    }
    /**
     * Create a popup for the specified marker.
     *
     * @param {HTMLElement} target
     * @param {Object} markerInfo
     * @param {Number} offset
     */
    createMarkerPopup(target, markerInfo, offset) {
        const partner = markerInfo.record.partner;
        const encodedAddress = encodeURIComponent(partner.contact_address_complete);
        return this.popover.open(target, {
            url: `https://www.google.com/maps/dir/?api=1&destination=${encodedAddress}`,
            ...this.getPopoverProps(markerInfo),
        });
    }

    onClickOpen(ev, ids) {
        this._openOnClick(ev, ids, "current");
    }

    onClickOpenUnlocated(ev, ids) {
        this._openOnClick(ev, ids, "dialog");
    }

    /**
     * @param {MouseEvent} ev
     * @param {number[]} ids
     * @param {'dialog'|'current'} defaultTarget
     */
    _openOnClick(ev, ids, defaultTarget) {
        if (ev.button === 0 || ev.button === 1) {
            const ctrlKey = isMacOS() ? ev.metaKey : ev.ctrlKey;
            const isMiddleClick = (ctrlKey && ev.button === 0) || ev.button === 1;
            const target = isMiddleClick ? "new_window" : defaultTarget;
            this.props.onMarkerClick(ids, target);
        }
    }
    /**
     * @param {Number} groupId
     */
    getGroupColor(groupId) {
        const index = Object.keys(this.props.model.data.recordGroups).indexOf(groupId);
        return colors[index % colors.length];
    }
    /**
     * Creates an array of latLng objects if there is located records.
     *
     * @returns {latLngBounds|boolean} objects containing the coordinates that
     *          allows all the records to be shown on the map or returns false
     *          if the records does not contain any located record.
     */
    getLatLng() {
        const tabLatLng = [];
        for (const record of this.props.model.data.records) {
            const partner = record.partner;
            if (partner && partner.partner_latitude && partner.partner_longitude) {
                tabLatLng.push(L.latLng(partner.partner_latitude, partner.partner_longitude));
            }
        }
        const { latitude, longitude } = this.props.model.data.userPosition;
        if (latitude && longitude) {
            tabLatLng.push(L.latLng(latitude, longitude));
        }
        if (!tabLatLng.length) {
            return false;
        }
        return L.latLngBounds(tabLatLng);
    }
    getMarkerPopupRecordData(record, locationOnly = true) {
        const fieldsView = [];
        if (!this.props.model.metaData.hideAddress) {
            if (record.partner.contact_address_complete) {
                fieldsView.push({
                    id: this.nextId++,
                    value: record.partner.contact_address_complete,
                    string: _t("Address"),
                });
            } else if (record.partner.partner_latitude && record.partner.partner_longitude) {
                fieldsView.push({
                    id: this.nextId++,
                    value:
                        record.partner.partner_latitude + ", " + record.partner.partner_longitude,
                    string: _t("Geolocation"),
                });
            }
        }
        if (locationOnly) {
            return fieldsView;
        }
        if (!this.props.model.metaData.hideName) {
            fieldsView.push({
                id: this.nextId++,
                value: record.display_name,
                string: _t("Name"),
            });
        }
        const fields = this.props.model.metaData.fields;
        for (const field of this.props.model.metaData.popover.fieldNodes) {
            if (record[field.fieldName]) {
                let value = record[field.fieldName];
                if (fields[field.fieldName].type === "many2one") {
                    value = record[field.fieldName].display_name;
                } else if (["one2many", "many2many"].includes(fields[field.fieldName].type)) {
                    value = record[field.fieldName]
                        ? record[field.fieldName].map((r) => r.display_name).join(", ")
                        : "";
                }
                fieldsView.push({
                    id: this.nextId++,
                    value,
                    string: field.string,
                });
            }
        }
        return fieldsView;
    }

    /**
     * Remove the markers from the map and empty the markers array.
     */
    removeMarkers() {
        for (const marker of this.markers) {
            marker.off("click");
            marker.off("mouseover");
            marker.off("mouseout");
            this.leafletMap.removeLayer(marker);
        }
        this.markers = [];
        this.markerByRecordId.clear();
        this.userPositionMarker = null;
    }
    /**
     * Remove the routes from the map and empty the the polyline array.
     */
    removeRoutes() {
        for (const polyline of this.polylines) {
            this.leafletMap.removeLayer(polyline);
        }
        this.polylines = [];
        this.polylineByGroupId.clear();
    }

    togglePinList(ev) {
        if (this.pinListPopover.isOpen) {
            this.state.expandedPinList = false;
            this.pinListPopover.close();
        } else {
            this.pinListPopover.open(ev.target, {
                model: this.props.model,
                renderer: this,
            });
            this.state.expandedPinList = true;
        }
    }

    /**
     * Starts the resize of the pin list sidebar (desktop only).
     *
     * @param {PointerEvent} ev
     */
    onStartResize(ev) {
        // Only triggered by left mouse button
        if (ev.button !== 0) {
            return;
        }
        const container = this.pinListContainerRef();
        ev.target.setPointerCapture(ev.pointerId);
        this.pinListResizeState = {
            container,
            mapArea: this.mapContainerRef().parentElement,
            initialX: ev.pageX,
            initialWidth: container.offsetWidth,
            maxWidth: this.getPinListMaxWidth(),
            rtl: getComputedStyle(container).direction === "rtl",
        };
        this.isResizingPinList = true;
        document.addEventListener("pointermove", this.onResizePinList, { capture: true });
        document.addEventListener("pointerup", this.onStopResizePinList, { capture: true });
        document.addEventListener("keydown", this.onStopResizePinList, { capture: true });
        this.clearResizeListeners = () => {
            document.removeEventListener("pointermove", this.onResizePinList, { capture: true });
            document.removeEventListener("pointerup", this.onStopResizePinList, { capture: true });
            document.removeEventListener("keydown", this.onStopResizePinList, { capture: true });
        };
    }

    /**
     * @param {PointerEvent} ev
     */
    onResizePinList = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const { container, mapArea, initialX, initialWidth, maxWidth, rtl } =
            this.pinListResizeState;
        // The sidebar sits after the map, so dragging towards the map widens it.
        const delta = (initialX - ev.pageX) * (rtl ? -1 : 1);
        const newWidth = Math.min(maxWidth, Math.max(PIN_LIST_MIN_WIDTH, initialWidth + delta));
        this.applyPinListWidth(newWidth, container, mapArea);
    };

    /**
     * @param {KeyboardEvent|PointerEvent} ev
     */
    onStopResizePinList = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.pointerId !== undefined) {
            ev.target.releasePointerCapture?.(ev.pointerId);
        }
        this.clearResizeListeners();
        this.isResizingPinList = false;
        this.pinListResizeState = null;
        // Remove the focus to make sure there is no focus inside the
        // now-resized sidebar (e.g. on the address input).
        document.activeElement.blur();
        this.leafletMap?.invalidateSize();
    };

    /**
     * Re-clamps the pin list sidebar's width if it no longer fits after the
     * browser window itself was resized.
     */
    onWindowResizePinList() {
        if (this.isResizingPinList) {
            return;
        }
        const container = this.pinListContainerRef();
        const maxWidth = this.getPinListMaxWidth();
        if (container && this.pinListWidth > maxWidth) {
            this.applyPinListWidth(maxWidth, container, this.mapContainerRef().parentElement);
        }
    }

    getPinListMaxWidth() {
        return Math.max(PIN_LIST_MIN_WIDTH, 0.5 * window.innerWidth);
    }

    applyPinListWidth(width, container, mapArea) {
        this.pinListWidth = width;
        container.style.width = `${width}px`;
        mapArea.style.width = `calc(100% - ${width}px)`;
        this.debouncedInvalidateMapSize();
    }

    /**
     * Update position in the map, markers and routes.
     */
    async updateMap() {
        if (this.forceFullUpdate || this.props.model.data.shouldUpdatePosition) {
            this.forceFullUpdate = false;
            const initialCoord = this.getLatLng();
            if (initialCoord) {
                this.leafletMap.flyToBounds(initialCoord, { animate: false });
            } else {
                this.leafletMap.fitWorld();
            }
            this.leafletMap.closePopup();
        }
        this.addMarkers();
        this.addRoutes();
    }

    /**
     * Updates the user location data with the specified
     * address, longitude and latitude. If no location
     * is specified, updates with the user's current
     * location. If location is empty, it will no longer
     * be visible on the map.
     *
     * @param {Location} location
     */
    async updateUserPosition(location) {
        await this.props.model.updateUserPosition(location);
        const coords = this.getLatLng();
        if (coords) {
            this.leafletMap.flyToBounds(coords, { animate: true });
        } else {
            this.leafletMap.fitWorld();
        }
    }

    /**
     * Center the map on a certain pin and open the popup linked to it.
     *
     * @param {Object} record
     */
    centerAndOpenPin(record) {
        if (this.pinListPopover.isOpen) {
            this.recordToOpen = record;
            this.pinListPopover.close();
        } else {
            this.centerAndOpenPinOnPatched(record);
        }
    }

    centerAndOpenPinOnPatched(record) {
        const px = this.leafletMap.project([
            record.partner.partner_latitude,
            record.partner.partner_longitude,
        ]);
        const latlng = this.leafletMap.unproject(px);
        // Only open the popover once the pin is centered to avoid re-position flickering
        if (this.openMarkerPopupOnMoveEnd) {
            this.leafletMap.off("moveend", this.openMarkerPopupOnMoveEnd);
        }
        this.openMarkerPopupOnMoveEnd = () => {
            this.createMarkerPopup(this.markerByRecordId.get(record.id).getElement(), {
                record: record,
                relatedRecords: [],
            });
        };
        this.leafletMap.once("moveend", this.openMarkerPopupOnMoveEnd);
        this.leafletMap.panTo(latlng, { animate: true, duration: 0.15 });
    }
}
