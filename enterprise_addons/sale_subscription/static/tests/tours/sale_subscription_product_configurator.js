import { registry } from '@web/core/registry';
import { stepUtils } from '@web_tour/tour_utils';
import configuratorTourUtils from '@sale/js/tours/product_configurator_tour_utils';
import subscriptionConfiguratorTourUtils from '@sale_subscription/../tests/tours/product_configurator_tour_utils';
import * as tourUtils from '@sale/js/tours/tour_utils';

registry
    .category('web_tour.tours')
    .add('sale_subscription_product_configurator', {
        steps: () => [
            ...stepUtils.goToAppSteps('sale_subscription.menu_sale_subscription_root', "Open the subscription app"),
            ...tourUtils.createNewSalesOrder(),
            ...tourUtils.selectCustomer("Test Partner"),
            ...tourUtils.addProduct("Main product"),
            // Assert that the default subscription prices and plans are correct.
            configuratorTourUtils.assertProductPrice("Main product", '5.00'),
            configuratorTourUtils.assertProductPriceInfo("Main product", "per week"),
            configuratorTourUtils.assertOptionalProductPrice("Optional product", '6.00'),
            subscriptionConfiguratorTourUtils.assertOptionalSubscriptionPlan("Optional product", "Weekly"),
            {
                content: "Discard the configurator",
                trigger: 'button:contains(Discard)',
                run: 'click',
            },
            {
                content: "Select another subscription plan",
                trigger: 'input#plan_id_0',
                run: 'edit 2 Months',
            },
            {
                trigger: 'ul.ui-autocomplete a:contains("2 Months")',
                run: 'click',
            },
            ...tourUtils.addProduct("Main product"),
            // Assert that the selected subscription prices and plans are correct.
            configuratorTourUtils.assertProductPrice("Main product", '15.00'),
            configuratorTourUtils.assertProductPriceInfo("Main product", "per 2 months"),
            configuratorTourUtils.assertOptionalProductPrice("Optional product", '16.00'),
            subscriptionConfiguratorTourUtils.assertOptionalSubscriptionPlan("Optional product", "2 Months"),
            ...configuratorTourUtils.saveConfigurator(),
            // Don't end the tour with a form in edition mode.
            ...stepUtils.saveForm(),
        ],
   });
