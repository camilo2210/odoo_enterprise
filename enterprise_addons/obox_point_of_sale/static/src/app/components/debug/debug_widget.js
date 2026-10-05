import { DebugWidget } from "@point_of_sale/app/utils/debug/debug_widget";
import { patch } from "@web/core/utils/patch";
import { OboxDebugPopup } from "../obox_debug_popup/obox_debug_popup";

patch(DebugWidget.prototype, {
    openOboxDebugPopup() {
        this.dialog.add(OboxDebugPopup);
    },
});
