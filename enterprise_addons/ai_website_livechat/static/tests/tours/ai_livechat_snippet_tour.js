import { deliverAIResults, setupAIResults } from "@ai/../tests/tours/ai_tour_helpers";
import {
    registerWebsitePreviewTour,
    insertSnippet,
    clickOnSnippet,
    changeOptionInPopover,
    clickOnSave,
} from "@website/js/tours/tour_utils";

registerWebsitePreviewTour(
    "ai_livechat_snippet_tour",
    {
        edition: true,
    },
    () => [
        ...insertSnippet({
            id: "s_ai_livechat",
            name: "AI Live Chat",
            groupName: "Contact & Forms",
        }),
        ...clickOnSnippet({ id: "s_ai_livechat", name: "AI Live Chat" }),
        ...changeOptionInPopover("AI Live Chat", "AI Agent", "Test Agent"),
        ...clickOnSave(),
        setupAIResults(":iframe .s_ai_livechat .ai_website_livechat_form textarea"),
        {
            content: "Enter a prompt",
            trigger: ":iframe .s_ai_livechat .ai_website_livechat_form textarea",
            run: "edit Hello && press Enter",
        },
        deliverAIResults(),
        {
            content: "Verify that the response is as expected",
            trigger:
                ":iframe .o_ai_livechat_message_with_copy_button:contains('This is a test response from AI.')",
        },
    ],
);
