import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("recurring_donation_use", {
    steps: () => [
        {
            content: "Open the recurrence plan dropdown",
            trigger: ".s_donation_recurrence_wrapper .dropdown-toggle",
            run: "click",
        },
        {
            content: "Select a recurring plan",
            trigger: ".s_donation_recurrence_wrapper .dropdown-item[data-value]",
            run(helpers) {
                const select = helpers.queryOne(".s_donation_recurrence_select");
                const plan = helpers.queryAll(".s_donation_recurrence_wrapper .dropdown-item")
                    .find((el) => el.dataset.value);
                select.value = plan.dataset.value;
            },
        },
        {
            content: "Select a prefilled donation amount",
            trigger: ".s_donation_btn[data-donation-value='10']",
            run: "click",
        },
        {
            content: "Donate with the selected plan",
            trigger: ".s_donation_donate_btn.o_ready_to_donate",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Check the recurring donation product is in the cart",
            trigger: ".o_cart_product:contains('Recurring Donation')",
        },
    ],
});
