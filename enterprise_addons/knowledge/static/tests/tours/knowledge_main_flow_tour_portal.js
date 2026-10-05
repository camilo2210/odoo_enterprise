/**
 * Global Knowledge flow tour - Adapter for portal user
 * Features tested:
 * - Create a private article
 * - Change its title / content
 * - Write on a "workspace" article to which we have access
 * - Create children articles to a "workspace" article to which we have access
 * - Favorite 2 different articles and invert their order in the favorite section
 */

import { dragAndDropArticle, checkTree } from "@knowledge/../tests/tours/knowledge_tour_utils";
import { location, browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

let workspaceArticleResId;
let privateArticleResId;

async function waitForArticleResId(retries = 10, delay = 50) {
    for (let i = 0; i < retries; i++) {
        const url = new URL(location);
        const id = extractURLResID(url);
        if (id) {
            return id;
        }
        await new Promise((resolve) => setTimeout(resolve, delay));
    }
    throw new Error(`Expected pathname like /knowledge/article/{id}, got ${location}`);
}

/**
 * Extract the resId from a Knowledge portal URL of scheme:
 * /knowledge/article/{resId}
 * @param {URL} url
 * @returns {Number} resId
 */
function extractURLResID(url) {
    return parseInt((url.pathname.match("/knowledge/article/([0-9]+)") || []).at(1));
}

registry.category("web_tour.tours").add('knowledge_main_flow_tour_portal', {
    steps: () => [{
    trigger: ".o_section_create",
    async run({ click }) {
        workspaceArticleResId = await waitForArticleResId();
        if (!workspaceArticleResId) {
            const url = new URL(location);
            throw new Error(`Expected pathname to be like /knowledge/article/{id}, got ${url.pathname} instead.`);
        }
        await click();
    },
}, {
    trigger: 'section[data-section="private"] .o_article .o_article_name:contains("Untitled")',
    async run() {
        const resId = await waitForArticleResId();
        if (resId !== workspaceArticleResId + 1) {
            const url = new URL(location);
            throw new Error(`Expected pathname to be like /knowledge/article/${workspaceArticleResId + 1}, got ${url.pathname} instead.`);
        }
    },  // check that the article is correctly created (private section)
}, {
    trigger: '.o_hierarchy_article_name > input',
    run: "edit My Private Article && click body",  // modify the article name
}, {
    trigger: '.note-editable.odoo-editor-editable',
    run: "editor Content of My Private Article",  // modify the article content
}, {
    content: "Internal Workspace Article is not supposed to be visible for portal user.",
    trigger: 'body:has(section[data-section="workspace"] .o_article .o_article_name:count(1))',
}, {
    trigger: '.o_knowledge_search', // make sure the search article feature works
    run: "click",
}, {
    trigger: ".o_article_search_dialog input",
    run: "edit Workspace Article",
}, {
    trigger: `.o_article_search_item:contains(Workspace Article)`,
    run: 'click',
}, {
    content: "wait for article to be correctly loaded",
    trigger: '.o_knowledge_editor:contains("Content of Workspace Article")',
}, {
    trigger: '.note-editable.odoo-editor-editable',
    run: "editor Edited Content of Workspace Article",  // modify the article content
}, {
    content: "Hover on Workspace Article to make create article visible",
    trigger: ".o_article:contains(Workspace Article)",
    run: "hover && click .o_article:contains(Workspace Article) .o_article_create",
}, {
    content: "Check that the article is correctly created (workspace section)",
    trigger: 'section[data-section="workspace"] .o_article .o_article_name:contains("Untitled")',
}, {
    content: "Modify the article name",
    trigger:
        ".o_knowledge_header:has(.o_hierarchy_item:contains(workspace article)) .o_hierarchy_article_name > input",
    run: "edit Child Article 1 && press Tab",
},
        checkTree({
            workspace: {
                label: "Workspace",
                children: [
                    {
                        label: "Workspace Article",
                        children: [{ label: "Child Article 1" }],
                    },
                ],
            },
            private: {
                label: "Private",
                children: [{ label: "My Private Article" }],
            },
        }),
{
    content: "create child article (2)",
    trigger: ".o_article:contains(Workspace Article)",
    run: "hover && click .o_article:contains(Workspace Article) .o_article_create",
},
{
    content: "Check that the article is correctly created (workspace section)",
    trigger: 'section[data-section="workspace"] .o_article .o_article_name:contains("Untitled")',
}, {
    content: "Modify the article name",
    trigger: '.o_hierarchy_article_name > input',
    run: "edit Child Article 2 && press Tab",
},
        checkTree({
            workspace: {
                label: "Workspace",
                children: [
                    {
                        label: "Workspace Article",
                        children: [{ label: "Child Article 1" }, { label: "Child Article 2" }],
                    },
                ],
            },
            private: {
                label: "Private",
                children: [{ label: "My Private Article" }],
            },
        }),
{
    content: "Go back to main workspace article",
    trigger: 'section[data-section="workspace"] .o_article .o_article_name:contains("Workspace Article")',
    run: "click",
}, {
    content: "Wait for article to be correctly loaded",
    trigger: '.o_knowledge_editor:contains("Edited Content of Workspace Article")',
}, {
    content: "Add to favorite",
    trigger: '.o_knowledge_toggle_favorite',
    run: "click",
}, {
    content: "Check article was correctly added into favorites",
    trigger: 'div.o_favorite_container .o_article .o_article_name:contains("Workspace Article")',
}, {
    content: "Go back to private article",
    trigger: 'section[data-section="private"] .o_article .o_article_name:contains("My Private Article")',
    run: "click",
}, {
    trigger: '.o_knowledge_editor:contains("My Private Article")',
    async run() {
        privateArticleResId = await waitForArticleResId();
        if (privateArticleResId === workspaceArticleResId) {
            throw new Error(`Expected private article resId ${privateArticleResId} to be different from workspace article resId ${workspaceArticleResId}.`);
        }
        browser.history.back();
    },  // wait for article to be correctly loaded and go back in the browser history
}, {
    trigger: '.o_knowledge_editor:contains("Edited Content of Workspace Article")',
    async run() {
        const resId = await waitForArticleResId();
        if (resId !== workspaceArticleResId) {
            throw new Error(`Expected to be back on the workspace article with resId ${workspaceArticleResId}, got ${resId} instead.`)
        }
        browser.history.forward();
    },  // wait for article to be correctly loaded and go forward in the browser history
}, {
    trigger: '.o_knowledge_editor:contains("My Private Article")',
    async run() {
        const resId = await waitForArticleResId();
        if (resId !== privateArticleResId) {
            throw new Error(`Expected to be back on the private article with resId ${privateArticleResId}, got ${resId} instead.`)
        }
    },  // wait for article to be correctly loaded
}, {
    // add to favorite
    trigger: '.o_knowledge_toggle_favorite',
    run: "click",
}, {
    // wait for the article to be registered as favorited
    trigger: '.o_knowledge_toggle_favorite [data-icon="star"].oi-filled',
}, {
    // move private article above workspace article in the favorite section
    trigger: 'div.o_favorite_container .o_article_handle:contains("My Private Article")',
    run: ({ queryOne }) => {
        dragAndDropArticle(
            queryOne('div.o_favorite_container .o_article_handle:contains("My Private Article")'),
            queryOne('div.o_favorite_container .o_article_handle:contains("Workspace Article")'),
        );
    },
}, {
    // verify that the move was done
    trigger: 'div.o_favorite_container ul li:first:contains("My Private Article")',
}]});
