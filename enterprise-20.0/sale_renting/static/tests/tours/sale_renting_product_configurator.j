import { registry } from '@web/core/registry';
import { stepUtils } from '@web_tour/tour_utils';
import configuratorTourUtils from '@sale/js/tours/product_configurator_tour_utils';
import * as tourUtils from '@sale/js/tours/tour_utils';

registry
    .category('web_tour.tours')
    .add('sale_renting_product_configurator', {
        steps: () => [
            ...stepUtils.goToAppSteps('sale_renting.rental_menu_root', "Open the rental app"),
            {
                content: "Create a new SO",
                trigger: '.o_list_button_add',
                run: 'click',
            },
            ...tourUtils.selectCustomer("Test Partner"),
            ...tourUtils.addProduct("Main product"),
            // Assert that the rental prices and durations are correct.
            configuratorTourUtils.assertProductPrice("Main product", '15.00'),
            configuratorTourUtils.assertProductPriceInfo("Main product", "Day"),
            configuratorTourUtils.assertOptionalProductPrice("Optional product", '16.00'),
            configuratorTourUtils.assertOptionalProductPriceInfo("Optional product", "Day"),
            ...configuratorTourUtils.saveConfigurator(),
            // Don't end the tour with a form in edition mode.
            ...stepUtils.saveForm(),
        ],
   });
