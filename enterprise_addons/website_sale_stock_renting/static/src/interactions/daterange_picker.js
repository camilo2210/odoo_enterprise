import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { _t } from '@web/core/l10n/translation';
import daterangePickerUtils from '@website_sale_renting/js/daterange_picker_utils';
import { DaterangePicker } from '@website_sale_renting/interactions/daterange_picker';

patch(DaterangePicker.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            _productEl: {
                't-on-product_added_to_cart': () => this._updateRentingProductAvailabilities(true),
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

    /**
     * Override of `website_sale_renting` to update the renting product availabilities when the
     * product changes.
     *
     * @param {CustomEvent} event
     */
    async onProductChanged(event) {
        const hasChanged = this.productId !== event.detail.productId;
        await super.onProductChanged(...arguments);
        if (hasChanged) {
            await this._updateRentingProductAvailabilities();
        }
    },

    /**
     * Override of `website_sale_renting` to take the product's stock into account.
     *
     * @param {DateTime} startDate
     * @param {DateTime} endDate
     * @param {Number} productId
     * @return {Boolean} - True if the rental dates are invalid, false otherwise.
     */
    canBeRented(startDate, endDate, productId=0) {
        const valid = super.canBeRented(...arguments);
        if (
            valid
            && startDate
            && endDate
            && this.preparationTime !== undefined
            && startDate < luxon.DateTime.now().plus({ hours: this.preparationTime })
        ) {
            this.env.services.notification.add(
                _t("Your rental product cannot be prepared as fast, please rent later."),
                { type: "warning" }
            );
            return false;
        }
        return valid;
    },

    _getExpectedEndDate(endDate) {
        const end = super._getExpectedEndDate(...arguments);
        if (daterangePickerUtils.isDurationWithHours(this.el)) {
            return end.plus({ hours: this.preparationTime });
        }
        return end;
    },
});
