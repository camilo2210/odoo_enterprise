import { registry } from '@web/core/registry';
import configuratorTourUtils from '@sale/js/tours/product_configurator_tour_utils';
import subscriptionConfiguratorTourUtils from '@sale_subscription/../tests/tours/product_configurator_tour_utils';
import * as wsTourUtils from '@website_sale/js/tours/tour_utils';

registry
    .category('web_tour.tours')
    .add('website_sale_subscription_product_configurator', {
        steps: () => [
            ...wsTourUtils.addToCart({ productName: "Main product", search: false, expectUnloadPage: true }),
            // Assert that the subscription prices and plans are correct.
            configuratorTourUtils.assertProductPrice("Main product", '5.00'),
            configuratorTourUtils.assertProductPriceInfo("Main product", "per week"),
            configuratorTourUtils.assertOptionalProductPrice("Optional product", '6.00'),
            subscriptionConfiguratorTourUtils.assertOptionalSubscriptionPlan("Optional product", "Weekly"),
            {
                content: "Proceed to checkout",
                trigger: 'button:contains(Go to Checkout)',
                run: 'click',
                expectUnloadPage: true,
            },
            {
                content: "Verify the subscription price in the cart",
                trigger: 'h6[name="website_sale_cart_line_price"]:contains(5.00)',
            },
            {
                content: "Verify the subscription plan in the cart",
                trigger: 'div[name="recurring_info"]:contains(per week)',
            },
        ],
   });
