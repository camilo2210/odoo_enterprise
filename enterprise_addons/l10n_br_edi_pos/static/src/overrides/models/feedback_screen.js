import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FeedbackScreen } from "@point_of_sale/app/screens/feedback_screen/feedback_screen";
import { useEffect } from "@odoo/owl";

patch(FeedbackScreen.prototype, {
    setup() {
        super.setup();
        useEffect(() => {
            if (this.loading() === false) {
                const error = this.currentOrder.l10n_br_avatax_error;
                if (error) {
                    this.dialog.add(
                        AlertDialog,
                        {
                            title: _t("NFCe error"),
                            body:
                                _t(
                                    `We could not send the NFCe for this order.\n\nTo send it, go to Orders or Backend > Paid Order or Orders > Select the Order > Details > Send NFCe.\n\n`
                                ) + error,
                        },
                        {}
                    );
                }
            }
        });
    },
});
