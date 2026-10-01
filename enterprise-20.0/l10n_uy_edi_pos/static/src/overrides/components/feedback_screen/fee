import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useEffect } from "@odoo/owl";
import { FeedbackScreen } from "@point_of_sale/app/screens/feedback_screen/feedback_screen";

patch(FeedbackScreen.prototype, {
    setup() {
        super.setup();
        useEffect(() => {
            if (this.loading() === false) {
                const error = this.currentOrder.l10n_uy_edi_error;
                if (this.pos.isUruguayanCompany() && error) {
                    this.dialog.add(AlertDialog, {
                        title: _t("CFE error"),
                        body: _t(
                            "The CFE of this order was not issued. The order can be sent again from Orders: select the order, then Send CFE.\n\n%s",
                            error
                        ),
                    });
                }
            }
        });
    },
});
