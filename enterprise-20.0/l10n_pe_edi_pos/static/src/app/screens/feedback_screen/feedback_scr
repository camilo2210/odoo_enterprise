import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useEffect } from "@odoo/owl";
import { FeedbackScreen } from "@point_of_sale/app/screens/feedback_screen/feedback_screen";

patch(FeedbackScreen.prototype, {
    setup() {
        super.setup();
        useEffect(() => {
            if (this.loading() === false && this.currentOrder.account_move) {
                if (
                    this.currentOrder.to_invoice &&
                    this.currentOrder.company.country_id.code === "PE" &&
                    this.currentOrder.account_move.l10n_pe_edi_warnings
                ) {
                    this.dialog.add(AlertDialog, {
                        title: _t("EDI Processing Issue"),
                        body: _t(
                            "The electronic invoice process returned an error.\nPlease review the invoice details from the backend to print the SUNAT compliant electronic document."
                        ),
                    });
                }
            }
        });
    },
});
