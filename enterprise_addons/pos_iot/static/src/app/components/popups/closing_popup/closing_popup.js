import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";

patch(ClosePosPopup.prototype, {
    async closeSession() {
        if (this.pos.config.iot_display_id) {
            const { iot_id, identifier } = this.pos.config.iot_display_id;
            this.pos.iotHttp.action(iot_id, identifier, { action: "update_url", url: "" });
        }
        await super.closeSession(...arguments);
    },
});
