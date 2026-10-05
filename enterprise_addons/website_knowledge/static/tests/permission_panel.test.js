import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { animationFrame, beforeEach, click, expect, test } from "@odoo/hoot";
import { signal } from "@odoo/owl";
import {
    defineModels,
    fields,
    makeMockServer,
    MockServer,
    models,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { getOrigin } from "@web/core/utils/urls";

const articleId = 1;
const articleUrl = `${getOrigin()}/knowledge/article/${articleId}`;
class KnowledgeArticle extends models.ServerModel {
    _records = [
        {
            id: articleId,
            article_url: articleUrl,
        },
    ];

    get_permission_panel_members() {
        return [];
    }
}

defineMailModels();
defineModels([KnowledgeArticle]);

/**
 * @param {(changes: any) => void} [onUpdate]
 */
async function mountPermissionPanel(onUpdate) {
    function load() {
        reactiveRecord.set(makeRecord());
    }
    function makeRecord() {
        return {
            data: env["knowledge.article"].browse(articleId)[0],
            load,
            update,
        };
    }
    function update(changes) {
        env["knowledge.article"].write(articleId, changes);
        load();
        onUpdate?.(changes);
    }

    const { env } = await makeMockServer();
    const reactiveRecord = signal(makeRecord());
    const pp = await mountWithCleanup(PermissionPanel, {
        props: {
            close: () => {},
            openArticle: () => {},
            reactiveRecord,
            sendArticleToTrash: () => {},
        },
    });
    await animationFrame();
    return pp;
}

beforeEach(() =>
    patch(navigator.clipboard, {
        writeText(value) {
            expect.step(`copy: ${value}`);
        },
    })
);

test("Publish an article", async () => {
    // FIXME: allows to be written on during the test
    // This is because writing on related fields does not work in the mock server
    KnowledgeArticle._fields.website_published = fields.Boolean({ related: false });
    KnowledgeArticle._records[0].user_can_write = true;
    await mountPermissionPanel(expect.step);
    await animationFrame();
    expect(
        ".knowledge_published_status_message:contains('Share to web') + .form-switch input"
    ).not.toBeChecked();
    await click(".o_knowledge_permission_panel .flex-grow-1");
    await animationFrame();
    await expect.waitForSteps([{ website_published: true }]);
    expect(
        ".knowledge_published_status_message:contains('Article shared to web') + .form-switch input"
    ).toBeChecked();
    await click(".o_clipboard_button");
    await expect.waitForSteps([`copy: ${articleUrl}`]);
    await click(
        ".knowledge_published_status_message:contains('Article shared to web') + .form-switch input"
    );
    await animationFrame();
    await expect.waitForSteps([{ website_published: false }]);
    expect(
        ".knowledge_published_status_message:contains('Share to web') + .form-switch input"
    ).not.toBeChecked();
    expect(".o_clipboard_button").toHaveCount(0);
});

test("Published readonly article", async () => {
    patch(user, { isAdmin: false });
    const pp = await mountPermissionPanel();
    await animationFrame();
    // toggle should not be shown as user can't publish the article
    expect(".form-switch").toHaveCount(0);
    // clicking on the publish section shouldn't do anything as user can't publish it
    await click(".o_knowledge_permission_panel .knowledge_published_status_message");
    await animationFrame();
    expect(".knowledge_published_status_message").toHaveText("Article not Published");
    // publish the article
    MockServer.env["knowledge.article"].write(articleId, { is_published: true });
    await pp.load();
    await animationFrame();
    expect(".knowledge_published_status_message").toHaveText("Article shared to web");
    await click(".o_clipboard_button");
    await expect.waitForSteps([`copy: ${articleUrl}`]);
});
