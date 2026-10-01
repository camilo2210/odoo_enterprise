import { patch } from "@web/core/utils/patch";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { registerSuccessAnimation } from "@pos_self_order_mobile/app/utils/kiosk_leds";
import { onMounted } from "@odoo/owl";

patch(selfOrderIndex.prototype, {
    setup() {
        super.setup(...arguments);

        // Uploading the frames takes a moment on the panel, so get it out of the way at load
        // rather than when a payment is accepted.
        onMounted(() => {
            if (this.selfOrder.kioskMode) {
                registerSuccessAnimation();
            }
        });
    },
});
