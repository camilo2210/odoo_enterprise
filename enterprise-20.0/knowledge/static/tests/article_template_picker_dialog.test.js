import { defineKnowledgeModels } from "@knowledge/../tests/knowledge_test_helpers";
import { ArticleTemplatePickerDialog } from "@knowledge/components/article_template_picker_dialog/article_template_picker_dialog";
import { animationFrame, click, expect, test } from "@odoo/hoot";
import { Component, t, useProps, xml } from "@odoo/owl";
import {
    assignDialogTestEnv,
    makeMockServer,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { patch } from "@web/core/utils/patch";
import { KnowledgeArticle } from "./mock_server/mock_models/knowledge_article";

defineKnowledgeModels();

test("preview becomes visible again after switching articles in the sidebar", async () => {
    KnowledgeArticle._records = [1, 2].map((id) => ({
        id,
        name: `Article ${id}`,
        body: `Body of Article ${id}`,
    }));

    class StubHtmlViewer extends Component {
        static template = xml`<div class="stub-html-viewer" t-out="this.props.config.value"/>`;

        props = useProps({
            config: t.object({
                value: t.string(),
            }),
        });
    }
    patch(ArticleTemplatePickerDialog, {
        components: {
            ...ArticleTemplatePickerDialog.components,
            KnowledgeHtmlViewer: StubHtmlViewer,
        },
    });

    const { env } = await makeMockServer();

    assignDialogTestEnv();
    await mountWithCleanup(ArticleTemplatePickerDialog, {
        props: {
            articles: env["knowledge.article"].search_read([], ["name"]),
            templates: [],
            onLoadArticle: () => {},
            onLoadTemplate: () => {},
            onDeleteArticle: () => {},
            onDeleteTemplate: () => {},
            close: () => {},
        },
    });
    await animationFrame();

    expect(".o_knowledge_template_preview").toBeVisible();
    expect(".stub-html-viewer").toHaveText("Body of Article 1");

    await click(".o_knowledge_template_selector li:nth-child(2)");
    await animationFrame();

    expect(".o_knowledge_template_preview").toBeVisible();
    expect(".stub-html-viewer").toHaveText("Body of Article 2");
});
