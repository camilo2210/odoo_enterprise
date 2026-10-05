import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";

patch(OpeningControlPopup.prototype, {
    async confirm() {
        if (this.pos.config.iot_display_id) {
            const { iot_id, identifier } = this.pos.config.iot_display_id;
            this.pos.iotHttp.action(iot_id, identifier, {
                action: "update_url",
                url: this.pos.customerDisplayUrl,
            });
        }
        await super.confirm(...arguments);
    },
});
