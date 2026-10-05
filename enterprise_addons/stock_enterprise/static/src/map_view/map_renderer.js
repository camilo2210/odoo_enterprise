/* global L */

import { renderToString } from "@web/core/utils/render";
import { MapRenderer, PIN_ICON_H } from "@web_map/map_view/map_renderer";

export class StockMapRenderer extends MapRenderer {
    static markerPopupTemplate = "stock_enterprise.markerPopup";

    /**
     * Create a popup for the specified marker.
     *
     * @param {Event} event
     * @param {Object} markerInfo
     * @param {Number} latLongOffset
     */
    createMarkerPopup(event, markerInfo, latLongOffset = 0) {
        const popupData = this.getMarkerPopupData(markerInfo);
        const partner = markerInfo.record.partner;
        const encodedAddress = encodeURIComponent(partner.contact_address_complete);
        const popupHtml = renderToString(this.constructor.markerPopupTemplate, {
            data: popupData,
            hasFormView: this.props.model.metaData.hasFormView,
            url: `https://www.google.com/maps/dir/?api=1&destination=${encodedAddress}`,
        });

        const popup = L.popup({ offset: [0, -PIN_ICON_H] })
            .setLatLng([
                partner.partner_latitude + latLongOffset,
                partner.partner_longitude - latLongOffset,
            ])
            .setContent(popupHtml)
            .openOn(this.leafletMap);

        const openBtn = popup
            .getElement()
            .querySelector("button.o-map-renderer--popup-buttons-open");
        if (openBtn) {
            openBtn.onclick = (ev) => this.onClickOpen(ev, markerInfo.ids);
            openBtn.onauxclick = (ev) => this.onClickOpen(ev, markerInfo.ids);
        }
        return popup;
    }

    getMarkerPopupData(markerInfo) {
        const records = markerInfo.relatedRecords.concat(markerInfo.record);
        const recordsView = [];

        for (const record of records) {
            recordsView.push({
                fields: this.getMarkerPopupRecordData(record, false),
                id: record.id,
            });
        }
        return recordsView;
    }
}
