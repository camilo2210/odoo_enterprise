/** @odoo-module **/

import { registry } from "@web/core/registry";
import { deliverAIResults, setupAIResults } from "@ai/../tests/tours/ai_tour_helpers";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("replace_knowledge_cover_with_ai_tour", {
    steps: () => [
        {
            content: "Open Knowledge App",
            trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
            run: "click",
        },
        {
            content: "Open Articles Menu",
            trigger: '.o_nav_entry[data-menu-xmlid="knowledge.knowledge_menu_article"]',
            run: "click",
        },
        {
            content: "Select the article 'Article with Cover'",
            trigger: ".o_data_cell:text(Article with Cover)",
            run: "click",
        },
        {
            content: "Hover over the Knowledge cover and click on Replace cover button",
            trigger: ".o_knowledge_cover",
            run: "hover && click .o_knowledge_option_button i[title='Change cover']",
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
            content: "Hover over the first AI generated image",
            trigger: ".o-mail-Message:contains('AI Generated 1') .o-mail-AttachmentList img",
            run: "hover",
        },
        {
            content: "Verify that 'Use This' button is visible and click on it",
            trigger: "button[name='media_dialog_use_this']:visible",
            run: "click",
        },
        ...stepUtils.saveForm(),
    ],
});
