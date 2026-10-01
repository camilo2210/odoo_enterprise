import { patch } from '@web/core/utils/patch';
import { AddToCart } from '@website_sale/interactions/add_to_cart';
import daterangePickerUtils from '@website_sale_renting/js/daterange_picker_utils';

patch(AddToCart.prototype, {
    /**
     * Override of `website_sale` to disable the daterange pickers after adding a product to the
     * cart.
     *
     * @param {MouseEvent} ev
     */
    async addToCart(ev) {
        const quantity = await this.waitFor(super.addToCart(...arguments));
        if (quantity > 0) {
            this.el.closest('.js_product')?.querySelectorAll(
                '.o_website_sale_daterange_picker_input'
            )?.forEach(el => el.disabled = true);
            document.querySelectorAll('.o_rental_info_message').forEach(
                el => el.classList.remove('d-none')
            );
        }
        return quantity;
    },

    /**
     * Override of `website_sale` to make the product container include the daterange picker on the cart page.
     *
     * @param {HTMLElement} el - The element containing the product.
     *
     * @returns {HTMLElement} - The closest element that contains both the product and the
     *     additional info needed to add the product to the cart.
     */
    _getProductContainer(el) {
        return super._getProductContainer(...arguments) ?? el.closest('.o_website_sale_checkout_container');
    },

    /**
     * Override of `website_sale` to add the renting pickup and return dates.
     *
     * @param {HTMLElement} el - The element containing the product.
     */
    _getOptionalParams(el) {
        const result = super._getOptionalParams(...arguments);
        const daterangePicker = el.querySelector('.o_website_sale_daterange_picker');
        if (daterangePicker) {
            Object.assign(result, daterangePickerUtils.getSerializedRentalDates(daterangePicker));
        }
        return result;
    },
});
