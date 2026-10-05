import { registry } from "@web/core/registry";
import { deliverAIResults, setupAIResults } from "@ai/../tests/tours/ai_tour_helpers";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("test_ai_draft_chatter_button", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            trigger: ".o_app[data-menu-xmlid='project.menu_main_pm']",
            run: "click",
        },
        {
            content: "Open the test project",
            trigger: ".o_kanban_view .o_kanban_record:contains(Test Project)",
            run: "click",
        },
        {
            content: "Open the test task",
            trigger: ".o_kanban_view .o_kanban_record:contains(Test Task)",
            run: "click",
        },
        {
            content: "Waiting for form view",
            trigger: ".o_form_view",
        },
        {
            content: "Click on the chatter's AI button",
            trigger: "button img.ai-systray-icon",
            run: "click",
        },
        setupAIResults(),
        {
            content: "Check that the second prompt button is correct",
            trigger: "div.o-mail-Thread button:contains('Write a followup answer')",
        },
        {
            content: "Click on the first prompt button to send the AI one of the default messages",
            trigger: "div.o-mail-Thread button:contains('Summarize the chatter conversation')",
            run: "click",
        },
        {
            content: "Check that the default message is shown",
            trigger: ".o-mail-Message-body:contains('Summarize the chatter conversation')",
        },
        deliverAIResults(),
        {
            content: "Check that the AI gives a reply",
            trigger: ".o-mail-Message-body:has(p:contains('This is dummy ai response'))",
        },
        {
            content: "Hover over the user message so its action buttons appear",
            trigger: ".o-mail-Message:eq(1)",
            run: "hover",
        },
        {
            content: "Check that the user message has the copy button",
            trigger: ".o-mail-Message:eq(1):has(button[name='copy-message'])",
        },
        {
            content: "Check that the user message doesn't have the send message button",
            trigger: ".o-mail-Message:eq(1):not(:has(button[name='send-message-direct']))",
        },
        {
            content: "Check that the user message doesn't have the log note button",
            trigger: ".o-mail-Message:eq(1):not(:has(button[name='log-note-direct']))",
        },
        {
            content: "Hover over the AI message so its action buttons appear",
            trigger: ".o-mail-Message:eq(2)",
            run: "hover",
        },
        {
            content: "Check that the AI message has the copy button",
            trigger: ".o-mail-Message:eq(2):has(button[name='copy-message'])",
        },
        {
            content: "Check that the AI message has the send message button",
            trigger: ".o-mail-Message:eq(2):has(button[name='send-message-direct'])",
        },
        {
            content: "Check that the AI message has the log note button",
            trigger: ".o-mail-Message:eq(2):has(button[name='log-note-direct'])",
        },
        {
            content: "Hover over the AI message so the action buttons appear",
            trigger: ".o-mail-Message:eq(2)",
            run: "hover",
        },
        {
            content: "Click on the send message button",
            trigger: "button[name='send-message-direct']",
            run: "click",
        },
        {
            content: "The message composer dialog should open",
            trigger: ".o_mail_composer_form_view",
        },
        {
            content: "The AI message should be posted in the composer dialog",
            trigger: ".odoo-editor-editable:eq(1):has(p:contains('This is dummy ai response'))",
        },
        {
            content: "The default recipients should be set in the composer dialog",
            trigger:
                ".o_mail_composer_form_view div[name='partner_ids'] .badge[data-tooltip='freddy@example.com']",
        },
        {
            content: "Close the composer dialog",
            trigger: ".btn-close",
            run: "click",
        },
        {
            content: "Hover over the AI message so the action buttons appear",
            trigger: ".o-mail-Message:eq(2)",
            run: "hover",
        },
        {
            content: "Click on the log note button",
            trigger: "button[name='log-note-direct']",
            run: "click",
        },
        {
            content: "The note composer dialog should open",
            trigger: ".o_mail_composer_form_view",
        },
        {
            content: "The AI message should be posted in the composer dialog",
            trigger: ".odoo-editor-editable:eq(1):has(p:contains('This is dummy ai response'))",
        },
        {
            content: "Click on the 'log' chatter button",
            trigger: "button:has(span:contains('Log'))",
            run: "click",
        },
        {
            content: "Check the the AI response was actually posted as a note",
            trigger: ".o-mail-Message-body:eq(0):has(p:contains('This is dummy ai response'))",
        },
        {
            content: "Close chat",
            trigger: ".o-mail-ChatWindow-header [data-icon='close_small']",
            run: "click",
        },
        ...stepUtils.toggleHomeMenu(),
        ...stepUtils.goToAppSteps("im_livechat.menu_livechat_root"),
        // chatbot script has no chatter but has a prompt button
        {
            trigger: ".o_menu_sections button[data-menu-xmlid='im_livechat.livechat_config']",
            run: "click",
        },
        {
            trigger: "a[data-menu-xmlid='im_livechat.chatbot_config']",
            run: "click",
        },
        {
            trigger: ".o_list_renderer .o_data_cell[name='title']",
            run: "click",
        },
        {
            content: "Waiting for form view",
            trigger: ".o_form_view",
        },
        {
            trigger: ".o_menu_systray button[title='Ask AI']",
            run: "click",
        },
        {
            content: "Chatter related prompt buttons should not be shown",
            trigger: ".o-mail-Thread:not(:has(button:contains('Write a followup answer')))",
        },
        {
            trigger: ".o-mail-Thread:not(:has(button:contains('Summarize the chatter')))",
        },
        {
            content: "The prompt button created for the agent should be shown",
            trigger: ".o-mail-Thread button:contains('chatbot prompt button')",
            run: "click",
        },
        deliverAIResults(),
        {
            trigger: ".o-mail-Message:contains('This is dummy ai response')",
            run: "hover",
        },
        {
            trigger:
                ".o-mail-Message:contains('This is dummy ai response') .o-mail-Message-actions",
        },
        {
            content: "Chatter related actions should not be shown",
            trigger:
                ".o-mail-Message:contains('This is dummy ai response'):not(:has(button[name='send-message-direct']))",
        },
        {
            trigger:
                ".o-mail-Message:contains('This is dummy ai response'):not(:has(button[name='log-note-direct']))",
        },
        {
            trigger: ".o-mail-ChatWindow-header [data-icon='close_small']",
            run: "click",
        },
        ...stepUtils.toggleHomeMenu(),
        ...stepUtils.goToAppSteps("crm.crm_menu_root"),
        {
            trigger: ".o_menu_sections button[data-menu-xmlid='crm.crm_menu_config']",
            run: "click",
        },
        // activity type has no chatter and no prompt button
        {
            trigger: "a[data-menu-xmlid='crm.crm_team_menu_config_activity_types']",
            run: "click",
        },
        {
            trigger: ".o_list_renderer .o_data_cell[name='name']",
            run: "click",
        },
        {
            content: "Waiting for form view",
            trigger: ".o_form_view",
        },
        {
            trigger: ".o_menu_systray button[title='Ask AI']",
            run: "click",
        },
        {
            content: "Chatter related prompt buttons should not be shown",
            trigger: ".o-mail-Thread:not(:has(button:contains('Write a followup answer')))",
        },
        {
            trigger: ".o-mail-Thread:not(:has(button:contains('Summarize the chatter')))",
        },
        {
            trigger: ".o-mail-Composer-inputContainer textarea",
            run: "edit Hi",
        },
        {
            trigger: ".o-mail-Composer-quickActions button[name='send-message']",
            run: "click",
        },
        deliverAIResults(),
        {
            trigger: ".o-mail-Message:contains('This is dummy ai response')",
            run: "hover",
        },
        {
            trigger:
                ".o-mail-Message:contains('This is dummy ai response') .o-mail-Message-actions",
        },
        {
            content: "Chatter related actions should not be shown",
            trigger:
                ".o-mail-Message:contains('This is dummy ai response'):not(:has(button[name='send-message-direct']))",
        },
        {
            trigger:
                ".o-mail-Message:contains('This is dummy ai response'):not(:has(button[name='log-note-direct']))",
        },
    ],
});

registry.category("web_tour.tours").add("test_ai_draft_html_field", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            trigger: ".o_app[data-menu-xmlid='project.menu_main_pm']",
            run: "click",
        },
        {
            content: "Open the test project",
            trigger: ".o_kanban_view .o_kanban_record:contains(Test Project)",
            run: "click",
        },
        {
            content: "Open the test task",
            trigger: ".o_kanban_view .o_kanban_record:contains(Test Task)",
            run: "click",
        },
        {
            content: "Click on the HTML editor to show power buttons",
            trigger: ".note-editable",
            run: "click",
        },
        {
            content: "Click on the ai powerbutton item",
            trigger: ".power_button[data-icon='o_ai_icon']",
            run: "click",
        },
        {
            content: "Check that the chat window appears",
            trigger: ".o-mail-ChatWindow.o-isAiComposer",
        },
        setupAIResults(),
        {
            content: "Write a message for the AI",
            trigger: "textarea.o-mail-Composer-input",
            run: "edit Generic prompt to AI",
        },
        {
            content: "Click on the send button to send the AI the default message",
            trigger: "button[name='send-message']",
            run: "click",
        },
        deliverAIResults(),
        {
            content: "Check that the AI gives a reply",
            trigger: ".o-mail-Message-body:has(p:contains('This is dummy ai response'))",
        },
        {
            content: "Hover over the user message so its action buttons appear",
            trigger: ".o-mail-Message:eq(1)",
            run: "hover",
        },
        {
            content: "Check that the user message has the copy button",
            trigger: ".o-mail-Message:eq(1):has(button[name='copy-message'])",
        },
        {
            content: "Check that the user message doesn't have the insert button",
            trigger: ".o-mail-Message:eq(1):not(:has(button[name='insertToComposer']))",
        },
        {
            content: "Hover over the AI message so its action buttons appear",
            trigger: ".o-mail-Message:eq(2)",
            run: "hover",
        },
        {
            content: "Check that the AI message has the copy button",
            trigger: ".o-mail-Message:eq(2):has(button[name='copy-message'])",
        },
        {
            content: "Check that the AI message has the insert button",
            trigger: ".o-mail-Message:eq(2):has(button[name='insertToComposer'])",
        },
        {
            content: "Hover over the AI message so the action button appear",
            trigger: ".o-mail-Message:eq(2)",
            run: "hover",
        },
        {
            content: "Click on the send message button",
            trigger: "button[name='insertToComposer']",
            run: "click",
        },
        {
            content: "Check the the AI response was actually inserted in the HTML field ",
            trigger: ".note-editable:has(div:contains('This is dummy ai response'))",
        },
        ...stepUtils.discardForm(),
    ],
});

registry.category("web_tour.tours").add("test_close_ai_chat_window", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        // open AI chat from systray
        {
            trigger: ".ai-systray-icon",
            run: "click",
        },
        {
            trigger: ".o-mail-ChatWindow",
        },
        // check no crash on close AI chat window
        {
            trigger: ".o-mail-ChatWindow button[title*='Close Chat Window']",
            run: "click",
        },
        {
            trigger: ".o-mail-ChatHub:not(:visible):not(:has(.o-mail-ChatWindow))",
        },
        // open again to be safe
        {
            trigger: ".ai-systray-icon",
            run: "click",
        },
        {
            trigger: ".o-mail-ChatWindow",
        },
        {
            trigger: ".o-mail-ChatWindow button[title*='Close Chat Window']",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("test_ai_systray_discuss_fullscreen", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Wait for Discuss to load in fullscreen",
            trigger: ".o-mail-Discuss",
        },
        {
            content: "Click on the AI systray button",
            trigger: ".ai-systray-icon",
            run: "click",
        },
        {
            content: "Verify that AI chat thread is opened in Discuss fullscreen",
            trigger: ".o-mail-DiscussContent .o-mail-Thread",
        },
        {
            content: "Verify the name of the AI agent opened from the systray",
            trigger: ".o-mail-DiscussContent-threadName[title='Odoo AI']",
        },
        {
            content: "Navigate away from Discuss to trigger the chat window",
            trigger: ".o_main_navbar .o_menu_toggle",
            run: "click",
        },
        {
            content: "Verify that the AI chat window is opened after leaving Discuss",
            trigger: ".o-mail-ChatWindow",
        },
    ],
});
