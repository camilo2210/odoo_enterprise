import { registry } from "@web/core/registry";
import { deliverAIResults, setupAIResults } from "@ai/../tests/tours/ai_tour_helpers";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("test_natural_language_query_with_date_groupby", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Wait for home screen to load",
            trigger: ".o_home_menu",
        },
        {
            content: "Click on the Ask AI button in the systray",
            trigger: ".o_menu_systray button:has(.ai-systray-icon)",
            run: "click",
        },
        {
            content: "Wait for AI chat to open",
            trigger: ".o-mail-ChatWindow",
        },
        setupAIResults(),
        {
            content: "Type the natural language query in the chat input",
            trigger: ".o-mail-ChatWindow .o-mail-Composer-input",
            run: "edit list of tasks grouped by month",
        },
        {
            content: "Send the message",
            trigger: ".o-mail-ChatWindow button[aria-label^='Send']",
            run: "click",
        },
        {
            content: "Wait for the user message to appear",
            trigger: ".o-mail-Message-content:contains('list of tasks grouped by month')",
        },
        deliverAIResults(),
        {
            content: "Check that the chat window title reflects the topic asked",
            trigger: ".o-mail-ChatWindow-header:contains('Monthly Task Analysis')",
        },
        {
            content: "Wait for list view to open",
            trigger: ".o_list_view",
        },
        {
            content: "Check that we're viewing project.task model",
            trigger: ".o_control_panel .o_breadcrumb .active:contains('Tasks')",
        },
        {
            content: "Check that date groupby facet exists in search bar",
            trigger: ".o_searchview .o_searchview_facet:contains('Deadline')",
        },
        {
            content: "Check that month interval is applied",
            trigger: ".o_searchview .o_searchview_facet:contains('Month')",
        },
        deliverAIResults(),
        {
            content: "Type second request in the existing chat window",
            trigger: ".o-mail-ChatWindow .o-mail-Composer-input",
            run: "edit switch to kanban view and filter by first quarter",
        },
        {
            content: "Send the second message",
            trigger: ".o-mail-ChatWindow button[aria-label^='Send']",
            run: "click",
        },
        {
            content: "Wait for the second user message to appear",
            trigger:
                ".o-mail-Message-content:contains('switch to kanban view and filter by first quarter')",
        },
        deliverAIResults(),
        {
            content: "Wait for kanban view to load",
            trigger: ".o_kanban_view",
        },
        {
            content: "Check that date filter facet for Q1 exists",
            trigger: ".o_searchview .o_searchview_facet:contains('Q1')",
        },
        deliverAIResults(),
        {
            content: "Verify we still have the deadline field in search",
            trigger: ".o_searchview .o_searchview_facet:contains('Deadline')",
        },
    ],
});
