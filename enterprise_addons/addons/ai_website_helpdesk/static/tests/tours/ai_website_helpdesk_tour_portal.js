import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

import "@website_helpdesk_knowledge/../tests/tours/helpdesk_knowledge_tour_portal";

patch(registry.category("web_tour.tours").get("access_helpdesk_article_portal_tour"), {
    steps() {
        const originalSteps = super.steps();
        const nextStep = originalSteps.findIndex(
            (step) => step.id === "menu_step",
        );
        return [
            ...originalSteps.slice(nextStep, 1),
            {
                content: "Ask AI",
                trigger: "textarea[name='promptInput']",
                run: "edit Article",
            }, {
                trigger: "button.ai_website_livechat_form_button",
                run: "click",
            },
            ...originalSteps.slice(5),
        ];
    },
});
