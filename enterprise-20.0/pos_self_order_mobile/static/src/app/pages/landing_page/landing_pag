import { patch } from "@web/core/utils/patch";
import { LandingPage } from "@pos_self_order/app/pages/landing_page/landing_page";
import { setCompanyColor } from "@pos_self_order_mobile/app/utils/kiosk_leds";
import { onWillStart } from "@odoo/owl";

patch(LandingPage.prototype, {
    setup() {
        super.setup(...arguments);

        onWillStart(() => {
            if (this.selfOrder.kioskMode) {
                setCompanyColor(this.selfOrder.config);
            }
        });
    },
});
