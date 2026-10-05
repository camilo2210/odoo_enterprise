import { InvoiceButton } from "@point_of_sale/app/screens/ticket_screen/invoice_button/invoice_button";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";

patch(InvoiceButton.prototype, {
    async onWillInvoiceOrder(order, partner) {
        if (this.pos.config.is_guatemalan_company) {
            if (this.pos._isUnidentifiedCustomerLimitExceeded(order)) {
                this.dialog.add(AlertDialog, {
                    title: _t("Limit Exceeded"),
                    body: _t(
                        "This order exceeds the maximum amount allowed for an unidentified customer.\nMaximum allowed amount: %(limit)s\nPlease select a customer with a valid Identification Type and Number before continuing.",
                        {
                            limit: formatMonetary(this.pos.config.l10n_gt_final_consumer_limit, {
                                currencyId: this.pos.currency.id,
                            }),
                        }
                    ),
                });
                return false;
            }
            if (
                this.props.order.isRefund &&
                !this.props.order.refunded_order_id?.is_singly_invoiced
            ) {
                this.dialog.add(AlertDialog, {
                    title: _t("Linked Order Not Invoiced"),
                    body: _t(
                        "The order linked to this refund has not been electronically invoiced. Please make sure the original order has an electronic invoice before trying to create an electronic credit note for this refund."
                    ),
                });
                return false;
            }
        }
        return await super.onWillInvoiceOrder(...arguments);
    },
});
