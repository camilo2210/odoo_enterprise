import { endKnowledgeTour } from '@knowledge/../tests/tours/knowledge_tour_utils';
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('helpdesk_insert_graph_view_in_knowledge', {
    steps: () => [{ // open the search menu
    trigger: '.o_control_panel .o_searchview_dropdown_toggler',
    run: "click",
}, { // open the priority submenu
    trigger: '.o_filter_menu .o_menu_item:contains("Priority")',
    run: "click",
}, { // pick a filter
    trigger: '.o_filter_menu .o_menu_item:contains("Priority") + * .dropdown-item:contains("Urgent")',
    run: "click",
}, { // check that the facet is now active
    trigger: '.o_searchview .o_facet_value:contains("Urgent")',
    run: "click",
}, { // close the modal to avoid it blocking the next step
    trigger: '.modal-header button.btn-close',
    run: "click",
}, { // reopen the search menu
    trigger: '.o_control_panel .o_searchview_dropdown_toggler',
    run: "click",
}, { // pick a group by
    trigger: '.o_group_by_menu .dropdown-item:contains("Team")',
    run: "click",
}, { // check that the facet is now active
    trigger: '.o_searchview .o_facet_value:contains("Team")',
    run: "click",
}, { // open the cog menu
    trigger: '.o_control_panel .o_cp_action_menus .dropdown-toggle',
    run: "click",
}, { // open the knowledge submenu
    trigger: ".dropdown-menu .dropdown-toggle:contains(Knowledge)",
    run: "hover",
}, { // insert the view in an article
    trigger: '.dropdown-menu .dropdown-item:contains("Insert view in article")',
    run: "click",
}, { // create a new article
    trigger: '.modal-footer button:contains("New")',
    run: "click",
}, { // wait for Knowledge to open
    trigger: '.o_knowledge_form_view',
    run: "click",
}, { // the user should be redirected to the new article
    trigger: '[data-embedded="view"]',
    run: function () {
        this.anchor.scrollIntoView();
    },
}, { // check that the embedded view has the selected facet
    trigger: '[data-embedded="view"] .o_searchview .o_facet_value:contains("Urgent")',
    run: "click",
}, {
    trigger: '[data-embedded="view"] .o_searchview .o_facet_value:contains("Team")',
    run: "click",
}, ...endKnowledgeTour()
]});
