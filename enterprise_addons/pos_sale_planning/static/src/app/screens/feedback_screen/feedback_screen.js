import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { FeedbackScreen } from "@point_of_sale/app/screens/feedback_screen/feedback_screen";

patch(FeedbackScreen.prototype, {
    clickEditPayment() {
        if (this.currentOrder.hasResourcePayment) {
            this.notification.add(
                _t(
                    "You cannot edit the payment if there is a resource-linked payment method on the order."
                ),
                {
                    type: "warning",
                }
            );
            return;
        }
        return super.clickEditPayment(...arguments);
    },
});
