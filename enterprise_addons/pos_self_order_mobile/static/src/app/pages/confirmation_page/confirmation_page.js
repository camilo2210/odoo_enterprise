import { patch } from "@web/core/utils/patch";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";
import { playSuccessAnimation } from "@pos_self_order_mobile/app/utils/kiosk_leds";
import { onMounted } from "@odoo/owl";

patch(ConfirmationPage.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => {
            if (this.selfOrder.kioskMode) {
                playSuccessAnimation();
            }
        });
    },
});
