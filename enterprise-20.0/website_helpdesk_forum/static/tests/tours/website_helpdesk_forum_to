import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("website_helpdesk_forum_tour", {
    steps: () => [
        {
            content: "Ask the question in this forum by clicking on the button.",
            trigger: ".o_wforum_ask_btn",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: "input[name=post_name]",
            content: "Give your post title.",
            run: "edit Test",
        },
        {
            content: "Put your question here.",
            trigger: ".note-editable p",
            run: "editor First Question <p>code here</p>",
        },
        {
            trigger: ".note-editable p:not(:has(br))",
        },
        {
            trigger: ".o_select_menu input",
            content: "Insert tags related to your question.",
            run: "edit Test",
        },
        {
            content: "Select found select menu item",
            trigger: ".o_popover.o_select_menu_menu .o_select_menu_item:contains('Test')",
            run: "click",
        },
        {
            trigger: "button:contains(/^Post/)",
            content: "Click to post your question.",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_wforum_question:contains(test user)",
        },
        {
            trigger: ".modal.modal_shown.show:contains(thanks for posting!) button.btn-close",
            run: "click",
        },
        {
            trigger: "a[id=dropdownMenuLink]",
            run: "click",
        },
        {
            trigger: ".create_ticket_forum",
            run: "click",
        },
        {
            trigger: "input[id=ticketTitle]",
            content: "Give your post title.",
            run: "edit Helpdesk Ticket(Test)",
        },
        {
            trigger: "button:contains(/^Create Ticket/)",
            run: "click",
        },
    ],
});
