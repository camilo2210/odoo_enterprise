import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(OrderSummary.prototype, {
    _setValue(val) {
        const selectedLine = this.currentOrder.getSelectedOrderline();
        if (
            this.pos.isScaleIconVisible &&
            ["quantity", "price"].includes(this.pos.numpadMode) &&
            !["quantity", "discount", "price"].includes(val)
        ) {
            const isZero = !val || val === "0";

            if (selectedLine.product_id.to_weight && !isZero) {
                this.numberBuffer.reset();
                this.dialog.add(
                    AlertDialog,
                    {
                        title: _t("Certified Scale error"),
                        body: _t("You cannot change the quantity of a weighed product."),
                    },
                    { onClose: this.props.close }
                );
                return;
            }
            if (isZero) {
                this.numberBuffer.reset();
                if (!selectedLine.uiState.isDeleted) {
                    selectedLine.uiState.isDeleted = true;
                    selectedLine.uiState.deletedWeightQuantityStr = selectedLine.quantityStr;
                    selectedLine.uiState.deletedWeightPriceStr = selectedLine.currencyDisplayPrice;
                    selectedLine.setQuantity(0);
                }
                return;
            }
        }
        super._setValue(val);
    },
});
