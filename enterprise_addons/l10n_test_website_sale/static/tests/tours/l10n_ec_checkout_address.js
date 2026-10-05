import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_checkout_address_ec", {
    steps: () => [
        ...tourUtils.addToCartFromProductPage(),
        tourUtils.goToCart({ quantity: 1 }),
        tourUtils.goToCheckout(),
        {
            content: "Check that the identification (VAT) field is present",
            trigger: "#o_vat",
        },
    ],
});

registry.category("web_tour.tours").add("tour_new_billing_ec", {
    steps: () => [
        ...tourUtils.addToCartFromProductPage(),
        tourUtils.goToCart({ quantity: 1 }),
        tourUtils.goToCheckout(),
        tourUtils.waitForInteractionToLoad(),
        {
            content: "Billing address is not same as delivery address",
            trigger: "#use_delivery_as_billing",
            run: "click",
        },
        {
            content: "Add new billing address",
            trigger: `#billing_address_list a[href^="/shop/address?address_type=billing"]:contains("Add")`,
            run: "click",
            expectUnloadPage: true,
        },
        ...tourUtils.fillAddressForm(
            {
                name: "John Doe",
                phone: "123456789",
                email: "johndoe@gmail.com",
                street: "1 rue de la paix",
                city: "Paris",
                zip: "75000",
            }
        ),
        {
            trigger: `[name="address_card"] address:contains(1 rue de la paix)`,
        },
    ],
});
