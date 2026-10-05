/** @odoo-module **/
import { registerWebsitePreviewTour, clickOnSave } from "@website/js/tours/tour_utils";
import { deliverAIResults, setupAIResults } from "@ai/../tests/tours/ai_tour_helpers";

registerWebsitePreviewTour(
    "replace_website_image_with_ai_tour",
    {
        edition: true,
    },
    () => [
        {
            content:
                "Double-click the image on the website to open the Media Dialog to replace the image",
            trigger: ":iframe #test_image",
            run: "dblclick",
        },
        {
            content: "Wait for Media Dialog to open and click on the AI button",
            trigger: ".o_select_media_dialog button[title='Generate Image with AI']",
            run: "click",
        },
        setupAIResults(),
        {
            content:
                "Click on the prompt button 'Help me generate an image' in the AI chat channel",
            trigger: ".ai-chat-prompt-button:contains('Help me generate an image')",
            run: "click",
        },
        {
            content: "Verify the message 'Help me generate an image' is posted in the chat channel",
            trigger: ".o-mail-Message:contains('Help me generate an image')",
        },
        deliverAIResults(),
        {
            content: "Click on the 'Use This' button",
            trigger: "button[name='media_dialog_use_this']:not(:visible)",
            run: "click",
        },
        {
            content: "Verify the image on the website is replaced by the first AI generated image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%201']",
        },
        {
            content: "Hover over the first AI generated image again",
            trigger: ".o-mail-Message:contains('AI Generated 1') .o-mail-AttachmentList img",
            run: "hover",
        },
        {
            content: "Verify that 'Try again' button is visible and click on it",
            trigger: "button[name='regenerate_image']:visible",
            run: "click",
        },
        deliverAIResults(),
        {
            content: "Click the 'Use This' button for the second AI generated image",
            trigger:
                ".o-mail-Message:contains('AI Generated 2') button[name='media_dialog_use_this']:not(:visible)",
            run: "click",
        },
        {
            content: "Verify the image on the website is replaced by the second AI generated image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%202']",
        },
        {
            content: "Focus the image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%202']",
            run: "click",
        },
        {
            content: "First Undo (Ctrl + z)",
            trigger: "body",
            run: "press ctrl+z",
        },
        {
            content: "Verify that the image on the website is the first AI generated image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%201']",
        },
        {
            content: "Second Undo (Ctrl + z)",
            trigger: "body",
            run: "press ctrl+z",
        },
        {
            content: "Verify the image on the website is the initial image",
            trigger: ":iframe #test_image",
        },
        {
            content: "First Redo (Ctrl + y)",
            trigger: "body",
            run: "press ctrl+y",
        },
        {
            content: "Verify the image on the website is the first AI generated image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%201']",
        },
        {
            content: "Second Redo (Ctrl + y)",
            trigger: "body",
            run: "press ctrl+y",
        },
        {
            content: "Verify the image on the website is the second AI generated image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%202']",
        },
        ...clickOnSave(),
        {
            content:
                "Verify the final image on the website after save is the second AI generated image",
            trigger: ":iframe img[data-original-src*='AI%20Generated%202']",
        },
    ],
);
