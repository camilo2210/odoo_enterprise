import { Navbar, BurgerMenuDialog } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { proxy } from "@odoo/owl";

patch(Navbar.prototype, {
    openCustomerDisplay() {
        if (this.pos.config.iot_display_id) {
            const { iot_id, identifier } = this.pos.config.iot_display_id;
            this.pos.iotHttp.action(iot_id, identifier, {
                action: "update_url",
                url: this.pos.customerDisplayUrl,
            });
        } else {
            super.openCustomerDisplay();
        }
    },
    async openLnaPopup() {
        for (const printer of [
            ...this.pos.config.receipt_printer_ids,
            ...this.pos.config.preparation_printer_ids,
        ]) {
            if (printer.iot_device_id && printer.iot_device_id.iot_id.use_lna) {
                const { iot_id, identifier } = printer.iot_device_id;
                await this.pos.iotHttp.action(iot_id, identifier, { action: "status" });
                break;
            }
        }
        return super.openLnaPopup();
    },
});

patch(BurgerMenuDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = proxy({ iotStatus: null });
        this.connectionStatus();
    },
    connectionStatus() {
        this.state.iotStatus = !this.pos.ui.isSmall && `(${this.pos.iotHttp.status})`;
        return true;
    },
});
