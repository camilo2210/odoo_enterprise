import { patch } from "@web/core/utils/patch";
import { Checkout } from "@website_sale/interactions/checkout";

patch(Checkout.prototype, {
    /**
     * Add country selector specific data to location selector.
     *
     * @override method from `@website_sale/interactions/checkout`
     */
    _prepareLocationDialogData(dataset) {
        const { isRental, fromDate, toDate } = dataset;
        const superDialogData = super._prepareLocationDialogData(dataset);
        if (isRental) {
            return {
                ...superDialogData,
                isRental: isRental,
                fromDate: fromDate,
                toDate: toDate,
            };
        }
        return superDialogData;
    },
});
