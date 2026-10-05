import { registry } from "@web/core/registry";
import { deliverAIResults, setupAIResults } from "@ai/../tests/tours/ai_tour_helpers";

/**
 * This tour sends the user message and asserts the graph view opens
 * with the date-groupby facet active.
 */
registry.category("web_tour.tours").add("ai_open_menu_graph_tour", {
    steps: () => [
        {
            trigger: ".o_navbar button[title='Ask AI']",
            run: "click",
        },
        setupAIResults(),
        {
            trigger: ".o-mail-ChatWindow .o-mail-Composer-input",
            run: "edit graph view of contacts per month",
        },
        {
            trigger: ".o-mail-ChatWindow .o-mail-Composer button[title^='Send']:enabled",
            run: "click",
        },
        deliverAIResults(),
        // Graph view must open via the action emitted by _ai_tool_open_menu_graph.
        {
            trigger: ".o_action_manager .o_graph_view",
        },
        // `applyAISearch` -> `createNewGroupBy('create_date', {interval:'month'})`
        {
            trigger: ".o_searchview .o_facet_values:contains(Created on: Month)",
        },
        deliverAIResults(),
        {
            trigger: ".o-mail-ChatWindow .o-mail-Message-body:contains(Here is your graph)",
        },
    ],
});
