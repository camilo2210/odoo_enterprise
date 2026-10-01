import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { ProductPage } from '@website_sale/interactions/product_page';
import daterangePickerUtils from '@website_sale_renting/js/daterange_picker_utils';

patch(ProductPage.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            '.o_website_sale_daterange_picker': {
                't-on-daterange_validity_changed': (ev) => {
                    this._toggleAddToCart(ev.currentTarget, ev.detail.isValid);
                },
                't-on-daterange_picker_applied': this.onChangeVariant.bind(this),
            },
        });
    },

    /**
     * Override of `website_sale` to set the URL search params based on the selected renting pickup
     * and return dates.
     */
    _setSearchParams() {
        super._setSearchParams(...arguments);
        const daterangePicker = this.el.querySelector('.o_website_sale_daterange_picker');
        if (daterangePicker) {
            const { start_date, end_date } = daterangePickerUtils.getSerializedRentalDates(daterangePicker);
            if (start_date && end_date) {
                const url = new URL(window.location);
                const searchParams = new URLSearchParams(window.location.search);
                searchParams.set('start_date', start_date);
                searchParams.set('end_date', end_date);
                // Avoid adding new entries in session history by replacing the current one
                history.replaceState(null, '', `${url.pathname}?${searchParams.toString()}`);
            }
        }
    },

    /**
     * Override of `website_sale` to update the renting info and verify the renting period when the
     * combination changes.
     *
     * @param {Event} ev
     * @param {Element} parent
     * @param {Object} combination
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);
        if (!combination.is_rental) return;
        const rentingDetails = parent.querySelector('.o_renting_details');
        const duration = rentingDetails?.querySelector('.o_renting_duration');
        const unit = rentingDetails?.querySelector('.o_renting_unit');
        if (combination.rental_duration > 1) {
            duration.textContent = combination.rental_duration;
        } else {
            duration.textContent = "";
        }
        if (unit) {
            unit.textContent = combination.rental_unit;
        }

        const daterangePickers = parent.querySelectorAll('.o_website_sale_daterange_picker');
        daterangePickers.forEach(el => el.dispatchEvent(new CustomEvent('combination_changed')));
    },

    /**
     * Override of `website_sale` to also store the rental minimum quantity, used by
     * `_toggleDisable` to disable the "Add to Cart" button when it isn't met.
     *
     * @param {Element} parent
     * @param {Object} combination
     */
    _updateMinimumQuantity(parent, combination) {
        super._updateMinimumQuantity(...arguments);
        if (!combination.is_rental) return;
        const minQtyInput = parent.querySelector('input[name="add_qty"]');
        minQtyInput.dataset.rentalMinimumQty = combination.minimum_rental_qty || 1;
    },

    /**
     * Override of `website_sale` to also disable the "Add to Cart" button of rental products when
     * the minimum quantity set by `_updateMinimumQuantity` isn't met.
     *
     * @param {Element} parent
     * @param {boolean} isCombinationPossible
     */
    _toggleDisable(parent, isCombinationPossible) {
        super._toggleDisable(...arguments);
        const minQtyInput = parent.querySelector('input[name="add_qty"]');
        const rentalMinimumQty = parseFloat(minQtyInput?.dataset?.rentalMinimumQty || 0);
        if (parseFloat(minQtyInput?.value || 0) < rentalMinimumQty) {
            parent.querySelectorAll('button[name="add_to_cart"]').forEach(
                el => el.disabled = true
            );
        }
    },

    /**
     * Override of `website_sale` to add the renting pickup and return dates to the optional
     * combination info parameters.
     *
     * @param {Element} product
     */
    _getOptionalCombinationInfoParams(product) {
        const result = super._getOptionalCombinationInfoParams(...arguments);
        const daterangePicker = product.querySelector('.o_website_sale_daterange_picker');
        if (daterangePicker) {
            Object.assign(result, daterangePickerUtils.getSerializedRentalDates(daterangePicker));
        }
        return result;
    },

    /**
     * Override of `website_sale` to never display rental combinations as out-of-stock.
     *
     * @param {Object} combination
     * @return {boolean}
     */
    _showOutOfStock(combination) {
        return super._showOutOfStock(...arguments) && !combination.is_rental;
    },

    /**
     * Toggle the "Add to Cart" button based on the validity of the renting period.
     *
     * @param {Element} parent - The parent element that triggered the event
     * @param {boolean} isValid - Whether the renting period is valid
     */
    _toggleAddToCart(parent, isValid) {
        const productEl = parent.closest(".js_product");
        const minQtyInput = productEl.querySelector('input[name="add_qty"]');
        const rentalMinimumQty = parseFloat(minQtyInput?.dataset?.rentalMinimumQty || 0);
        const isMinimumQtyMet = parseFloat(minQtyInput?.value || 0) >= rentalMinimumQty;
        productEl.querySelectorAll('button[name="add_to_cart"]').forEach(
            (el) => (el.disabled = !isValid || !isMinimumQtyMet)
        );
    },
});
