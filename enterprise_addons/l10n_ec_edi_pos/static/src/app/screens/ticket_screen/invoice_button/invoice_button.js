import { InvoiceButton } from "@point_of_sale/app/screens/ticket_screen/invoice_button/invoice_button";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(InvoiceButton.prototype, {
    async click() {
        if (this.pos.isEcuadorianCompany()) {
            if (
                this.props.order.priceIncl > this.pos.config.l10n_ec_consumer_final_limit &&
                this.props.order.getPartner().vat === "9999999999999" // This compliance is for the VAT number, not only for the final consumer.
            ) {
                this.pos.dialog.add(AlertDialog, {
                    body: _t(
                        "This order exceeds the maximum amount allowed for an unidentified consumer.\nPlease select the real customer with a valid RUC/ID before continuing."
                    ),
                });
                return false;
            }
        }
        return super.click();
    },
});
