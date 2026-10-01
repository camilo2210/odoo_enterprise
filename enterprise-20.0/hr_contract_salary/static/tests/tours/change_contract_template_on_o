import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry
    .category("web_tour.tours")
    .add("change_contract_template_on_offer_tour", {
        steps: () => ([
                {
                    content: "If there are too many smart buttons, open the More dropdown to avoid missing the Generate Offer button",
                    trigger: ".o_control_panel_main",
                    run: function (actions) {
                        const more_smart_button = this.anchor.querySelectorAll('.o_button_more');
                        if (more_smart_button.length!=0) {
                            actions.click(".o_button_more");
                        }
                    },
                },
                {
                    trigger: 'button[name="action_generate_offer"]',
                    content: 'Click on "Offer" smart button',
                    run: "click",
                },
                {
                    trigger: "#contract_template_id_0",
                    content: 'Click on the "Contract Template" select input',
                    run: "click",
                },
                {
                    trigger: "a:contains(Pokémon Trainer)",
                    content: 'Change "Contract Template" select input\'s value',
                    run: "click",
                },
                ...stepUtils.saveForm(),
            ]),
        },
    );
