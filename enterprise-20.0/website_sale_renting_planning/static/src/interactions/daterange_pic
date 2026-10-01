import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from "@web/public/utils";
import { DaterangePicker } from '@website_sale_renting/interactions/daterange_picker';

patch(DaterangePicker.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            _root: {
                "t-on-daterange_picker_applied": this.setAddQtyInputMax.bind(this),
            },
        });
    },

    /**
     * Override to get the renting product availabilities.
     */
    async willStart() {
        await this.waitFor(super.willStart());
        await this._updateRentingProductAvailabilities();
    },

    async _updateRentingProductAvailabilities(force = false) {
        await super._updateRentingProductAvailabilities(force);
        this.setAddQtyInputMax();
    },

    setAddQtyInputMax() {
        if (this.rentingAvailabilities[this.productId]) {
            const addQtyInput = this.dynamicSelectors
                ._productEl()
                .querySelector("input[name='add_qty']");
            if (!addQtyInput) {
                return;
            }
            const qty = parseFloat(addQtyInput.value) || 1;
            let availableQty = Infinity;
            for (const interval of this.rentingAvailabilities[this.productId]) {
                if (interval.start < this.endDate) {
                    if (interval.end > this.startDate) {
                        availableQty = Math.min(interval.quantity_available, availableQty);
                    }
                } else {
                    break;
                }
            }
            addQtyInput.dataset.max = Math.max(availableQty, 1);
            if (qty > availableQty) {
                addQtyInput.value = addQtyInput.dataset.max;
            }
        }
    },
});
