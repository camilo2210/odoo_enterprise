import { patch } from '@web/core/utils/patch';
import { AddToCart } from '@website_sale/interactions/add_to_cart';

patch(AddToCart.prototype, {
    /**
     * Override of `website_sale` to disable the subscription selector after adding a product to the
     * cart.
     *
     * @param {MouseEvent} ev
     */
    async addToCart(ev) {
        const productEl = ev.currentTarget.closest('.js_product');
        const quantity = await this.waitFor(super.addToCart(...arguments));
        if (quantity > 0 && productEl) {
            const inputs = productEl.querySelectorAll('input[name="plan_id"]');
            inputs.forEach(input => input.disabled = !input.checked);
            this._handleAddSubscriptionProduct(productEl);
        }
        return quantity;
    },

    _handleAddSubscriptionProduct(el) {
        const regularDeliveryCheckbox = el.querySelector('#regular_delivery');
        const oneTimeSaleCheckbox = el.querySelector('#allow_one_time_sale');

        const regularDeliverySection = el.querySelector('.regular-delivery');
        const oneTimeSaleSection = el.querySelector('.one-time-sale');

        const isRegularChecked = regularDeliveryCheckbox?.checked;
        const isOneTimeChecked = oneTimeSaleCheckbox?.checked;

        if (regularDeliverySection) {
            regularDeliverySection.style.display = isRegularChecked ? '' : 'none';
        }

        if (oneTimeSaleSection) {
            oneTimeSaleSection.style.display = (isOneTimeChecked && !isRegularChecked) ? '' : 'none';
        }
    },

    /**
     * Override of `website_sale` to add the subscription plan id.
     *
     * @param {HTMLElement} el - The element containing the product.
     */
    _getOptionalParams(el) {
        const result = super._getOptionalParams(...arguments);
        const selectedPlanId =
            el.querySelector('input[name="plan_id"]:checked')?.value
            ?? el.querySelector(
                'button[name="add_to_cart"][data-action="add_to_cart"]'
            )?.dataset?.subscriptionPlanId;
        if (selectedPlanId) {
            const allowOneTimeSale = el.querySelector('.allow_one_time_sale')?.checked;
            const planId = allowOneTimeSale ? null : parseInt(selectedPlanId);
            Object.assign(result, {
                plan_id: planId,
                allow_one_time_sale: allowOneTimeSale,
            });
        }
        return result;
    },
});
