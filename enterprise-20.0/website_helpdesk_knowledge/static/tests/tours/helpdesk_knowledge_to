import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('access_helpdesk_article_portal_tour', {
    steps: () => [{
    id: "menu_step",
    content: "clik on 'Help'",
    trigger: 'a[role="menuitem"]:contains("Help")',
    run: "click",
    expectUnloadPage: true,
}, {
    content: "Write 'Article' in the search bar",
    trigger: 'input[name="search"]',
    run: "edit Article",
}, {
    content: "Check that results contain 'Helpdesk Article'",
    trigger: '.o_search_result_item:contains("Helpdesk Article")',
}, {
    content: "Check that results contain 'Child Article'",
    trigger: '.o_search_result_item:contains("Child Article")',
}, {
    content: "Check that results don't contain 'Other Article'",
    trigger: '.o_dropdown_menu:not(:has(.o_search_result_item:contains("Other Article")))',
}]});
