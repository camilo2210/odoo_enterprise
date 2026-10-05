/**
 * Global Knowledge flow tour.
 * Features tested:
 * - Create an article
 * - Change its title / content
 * - Share an article with a created partner
 * - Create 2 children articles and invert their order
 * - Favorite 2 different articles and invert their order in the favorite section
 */

import {
    dragAndDropArticle,
    endKnowledgeTour,
} from "@knowledge/../tests/tours/knowledge_tour_utils";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

function checkArticle(section, ...articles) {
    let trigger = `section[data-section="${section}"]`;
    articles.forEach((article) => {
        const [eq, name] = article.split("|");
        trigger += ` > ul li:eq(${eq}):contains(${name})`;
    });
    return {
        content: `Check that section ${section} has `,
        trigger,
    };
}

function clickOnArticle(...args) {
    return {
        ...checkArticle(...args),
        run: "click",
    };
}

function waitUntilArticle(hierarchies) {
    return {
        content: `Wait the good article is in DOM`,
        trigger: `.o_form_editable:has(.o_hierarchy_item:count(${hierarchies.length}))`,
        async run({ waitUntil, queryAll }) {
            await waitUntil(
                () => {
                    const items = queryAll(`.o_hierarchy_item`);
                    const items_text = items.map((item) => item.textContent);
                    return JSON.stringify(items_text) === JSON.stringify(hierarchies);
                },
                {
                    timeout: 3000,
                    message: "Hierarchy of article is not good",
                }
            );
        },
    };
}

function waitUntilAutofocusOnEditorEditable() {
    return {
        content: `Wait for autofocus on editor editable`,
        trigger: `.note-editable.odoo-editor-editable`,
        async run({ waitUntil, queryFirst }) {
            await waitUntil(
                () => queryFirst(document.getSelection().anchorNode, { root: this.anchor }),
                {
                    timeout: 3000,
                    message: "The autofocus doesn't work",
                }
            );
        },
    };
}

registry.category("web_tour.tours").add("knowledge_main_flow_tour", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            // open Knowledge App
            trigger: '.o_app[data-menu-xmlid="knowledge.knowledge_menu_root"]',
            run: "click",
        },
        {
            // click on the "New Article" action
            trigger: ".o_knowledge_create_article",
            run: "click",
        },
        checkArticle("private", "0|Untitled"),
        waitUntilArticle(["Untitled"]),
        waitUntilAutofocusOnEditorEditable(),
        {
            trigger: ".note-editable.odoo-editor-editable h1",
            run: "editor My Private Article", // modify the article content
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        checkArticle("private", "0|My Private Article"),
        {
            trigger: 'section[data-section="workspace"]',
            run: "hover && click section[data-section=workspace] .o_section_create",
        },
        checkArticle("workspace", "1|Untitled"),
        waitUntilArticle(["Untitled"]),
        waitUntilAutofocusOnEditorEditable(),
        {
            trigger: ".o_hierarchy_article_name > input",
            run: "edit My Workspace Article && click body", // modify the article name
        },
        {
            trigger: ".note-editable.odoo-editor-editable",
            run: "editor Content of My Workspace Article", // modify the article content
        },
        {
            trigger: '.o_article:contains("My Workspace Article")',
            run: "hover && click .o_article:contains(My Workspace Article) .o_article_create",
        },
        checkArticle("workspace", "1|Untitled"),
        waitUntilArticle(["My Workspace Article/", "Untitled"]),
        waitUntilAutofocusOnEditorEditable(),
        {
            content: "modify the article name with Child Article 1",
            trigger: ".o_hierarchy_article_name > input",
            run: "edit Child Article 1 && click body",
        },
        checkArticle("workspace", "1|My Workspace Article", "0|Child Article 1"),
        {
            trigger: '.o_article:contains("My Workspace Article")',
            run: "hover && click .o_article:contains(My Workspace Article) .o_article_create",
        },
        clickOnArticle("workspace", "1|My Workspace Article", "1|Untitled"),
        waitUntilArticle(["My Workspace Article/", "Untitled"]),
        waitUntilAutofocusOnEditorEditable(),
        {
            content: "modify the article name",
            trigger: ".o_hierarchy_article_name > input",
            run: "edit Child Article 2 && click body",
        },
        {
            content: "check article 2 is in sidebar",
            trigger:
                ".o_knowledge_sidebar .o_knowledge_tree .o_section:eq(0) .o_article:contains(child article 2):not(:has(li))",
        },
        {
            content: "move child article 2 above child article 1",
            trigger: '.o_article_handle:contains("Child Article 2")',
            run: ({ queryOne }) => {
                dragAndDropArticle(
                    queryOne('.o_article_handle:contains("Child Article 2")'),
                    queryOne('.o_article_handle:contains("Child Article 1")')
                );
            },
        },
        checkArticle("workspace", "1|My Workspace Article", "0|Child Article 2"),
        checkArticle("workspace", "1|My Workspace Article", "1|Child Article 1"),
        clickOnArticle("workspace", "1|My Workspace Article"),
        waitUntilArticle(["My Workspace Article"]),
        {
            content: "open the share dropdown",
            trigger: '.o_knowledge_header .btn:contains("Share")',
            run: "click",
        },
        {
            content: "click on 'Share'",
            trigger: '.o_knowledge_permission_panel .btn:contains("Share")',
            run: "click",
        },
        {
            content: "Type the invited person's name",
            trigger: ".o_field_many2many_tags_email[name=partner_ids] input",
            run: "edit micheline@knowledge.com",
        },
        {
            content: "Open the simplified create form view",
            trigger: ".o-autocomplete--dropdown-menu .o_m2o_dropdown_option_create_edit a",
            run: "click",
        },
        {
            content: "Save the new partner",
            trigger:
                ".modal:has(.modal-header:contains(create recipients)) .o_form_button_save:contains(save)",
            run: "click",
        },
        {
            trigger:
                ".modal:has(.modal-header:contains(Share)) .o_field_tags .o_badge_text:text(micheline@knowledge.com)",
        },
        {
            content: "Submit the invite wizard",
            trigger: ".modal:has(.modal-header:contains(Share)) button:contains(Share)",
            run: "click",
        },
        {
            trigger: "body:not(:has(.modal))",
        },
        {
            trigger:
                ".o_knowledge_permission_panel_members span:contains('micheline@knowledge.com')",
        },
        {
            // add to favorite
            trigger: ".o_knowledge_toggle_favorite",
            run: "click",
        },
        checkArticle("favorites", "0|My Workspace Article"),
        clickOnArticle("private", "0|My Private Article"),
        waitUntilArticle(["My Private Article"]),
        {
            // add to favorite
            trigger: ".o_knowledge_toggle_favorite",
            run: "click",
        },
        {
            // wait for the article to be registered as favorited
            trigger: ".o_knowledge_toggle_favorite [data-icon='star']",
        },
        {
            // move private article above workspace article in the favorite section
            trigger:
                'section[data-section="favorites"] .o_article_handle:contains("My Private Article")',
            run: ({ queryOne }) => {
                dragAndDropArticle(
                    queryOne(
                        'section[data-section="favorites"] .o_article_handle:contains("My Private Article")'
                    ),
                    queryOne(
                        'section[data-section="favorites"] .o_article_handle:contains("My Workspace Article")'
                    )
                );
            },
        },
        checkArticle("favorites", "0|My Private Article"),
        clickOnArticle("workspace", "1|My Workspace Article"),
        waitUntilArticle(["My Workspace Article"]),
        {
            // click on the "New Article" action
            trigger: ".o_knowledge_create_article",
            run: "click",
        },
        checkArticle("private", "1|Untitled"),
        waitUntilArticle(["Untitled"]),
        waitUntilAutofocusOnEditorEditable(),
        {
            trigger: ".o_hierarchy_article_name > input",
            run: "edit Article to be moved && click body", // modify the article name
        },
        {
            // move article
            trigger: ".o_knowledge_header .dropdown-toggle",
            run: "click",
        },
        {
            trigger: '.dropdown-item:contains("Move To")',
            run: "click",
        },
        {
            content: "Make sure the dropdown menu is open",
            trigger: ".o-dropdown--menu.dropdown-menu",
        },
        {
            trigger: '.o_select_menu_item:contains("Article 3")',
        },
        {
            trigger: '.o_select_menu_item:contains("Article 3")',
            run: "click",
        },
        {
            trigger: '.o_select_menu_toggler:contains("Article 3")',
        },
        {
            trigger: '.modal-content .btn-primary:contains("Move Article")',
            run: "click",
        },
        {
            trigger:
                'section[data-section="workspace"] .o_article .o_article_name:contains("Article to be moved")',
            run: "click",
        },
        {
            // open trash
            trigger: '.o_knowledge_sidebar_trash a:contains("Trash")',
            run: "click",
        },
        {
            trigger: '.o_breadcrumb .active:contains("Trash")',
        },
        {
            // verify that the trash list has been opened correctly and that items are correctly ordered
            trigger: '.o_data_row:first .o_data_cell[name="display_name"]:contains("Article 2")',
        },
        ...endKnowledgeTour(),
    ],
});
