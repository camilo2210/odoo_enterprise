import { registry } from '@web/core/registry';
import * as tourUtils from '@website_sale/js/tours/tour_utils';
import * as rentalUtils from '@website_sale_renting/../tests/tours/tour_utils';


/**
 * Tests that css_not_available class is applied (removed) when picking an invalid (valid) rental
 * period.
 */
registry
    .category('web_tour.tours')
    .add('website_sale_renting_select_wrong_period', {
        steps: () => [
            {
                content: 'Select Computer',
                trigger: '.oe_product_cart:first a:contains("Computer")',
                run: 'click',
                expectUnloadPage: true,
            },
            tourUtils.waitForInteractionToLoad(),
            {
                content: 'Pick an invalid start date',
                trigger: 'input[name=renting_start_date]',
                run: 'edit 01/01/2000 && press Tab',
            },
            {
                content: 'Check that the add to cart button is disabled',
                trigger: 'button[name="add_to_cart"][disabled]',
            },
            ...rentalUtils.chooseFutureRentalDates({ duration: { days: 3 }, select_hours: false }),
            {
                content: 'Check that the add to cart button is enabled',
                trigger: 'button[name="add_to_cart"]:not([disabled])',
            },
        ],
   });
