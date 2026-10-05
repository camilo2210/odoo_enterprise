import { patch } from '@web/core/utils/patch';
import { ProductPage } from '@website_sale/interactions/product_page';
import { renderToElement } from "@web/core/utils/render";

patch(ProductPage.prototype, {
    /**
     * Override of `website_sale` to update the subscription info when the combination changes.
     *
     * @param {Event} ev
     * @param {Element} parent
     * @param {Object} combination
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);
        if (!combination.is_subscription) return;

        const price = parent.querySelector('.o_subscription_price')
            || parent.querySelector('.product_price h5');
        const addToCartButton = parent.querySelector(
            'button[name="add_to_cart"][data-action="add_to_cart"]'
        );
        const pricingSelect =
        parent.querySelector(".js_product h5:has(.o_subscription_price)") ||
        parent.querySelector(".js_product .plan_select");
        const oneTimePrice = parent.querySelector(".one_time_price .oe_currency_value");

        if (pricingSelect) {
        const disabledPlanIds = Array.from(
            pricingSelect.querySelectorAll("input[type='radio']:disabled"),
            radioButton => +radioButton.value
        );
        if (disabledPlanIds.length) {
            combination.pricings.forEach(pricing => {
                if (disabledPlanIds.includes(pricing.plan_id)) pricing.can_be_added = false;
            });
        }
        pricingSelect.replaceWith(
            renderToElement("website_sale_subscription.SubscriptionPricingTableSelect", {
                combination_info: combination,
            })
        );
    } else {
        // we don't find the element in the dom which means there was no pricings in the previous combination so there is no `Radio buttons` or `h5` elements to replace then we append one.
        const nodeToAppend = parent.querySelector(".one-time-sale")?.parentElement || parent.querySelector(".js_product div div");
        nodeToAppend.append(
            renderToElement("website_sale_subscription.SubscriptionPricingTableSelect", {
                combination_info: combination,
            })
        );
    }
        if (combination.allow_one_time_sale && oneTimePrice) {
            // update the one time price dynamically when changing variants.
            oneTimePrice.textContent = combination["list_price"].toFixed(
                combination.currency_precision
            );
            parent.querySelector('.product_price')?.classList?.remove('d-inline-block');
        }

        if (addToCartButton) {
            addToCartButton.dataset.subscriptionPlanId = combination.pricings.length > 0
                ? combination.subscription_default_pricing_plan_id : '';
        }
        if (price) {
            price.textContent = combination.subscription_default_pricing_price;
        }
    },

    /**
     * Override of `website_sale` to add the selected plan to the optional combination info
     * parameters.
     *
     * @param {Element} product
     */
    _getOptionalCombinationInfoParams(product) {
        const result = super._getOptionalCombinationInfoParams(...arguments);
        Object.assign(result, {
            'plan_id': product.querySelector('input[name="plan_id"]:checked')?.value
        });
        return result;
    },
});
