import { fields, models } from "@web/../tests/web_test_helpers";
import { KnowledgeArticle } from "@knowledge/../tests/mock_server/mock_models/knowledge_article";

export class DocumentsMixinTestModel extends models.Model {
    _name = "documents.mixin.test.model";

    name = fields.Char();
    document_count = fields.Integer();
}

/** Article in which the view is inserted, and from which it is loaded back. */
export class KnowledgeArticleEmbedding extends KnowledgeArticle {
    _records = [
        {
            id: 1,
            name: "Article 1",
            body: "<p><br></p>",
            is_template: false,
            user_has_write_access: true,
        },
    ];
    _views = {
        form: /* xml */ `
            <form js_class="knowledge_article_view_form">
                <sheet>
                    <field name="name" invisible="1"/>
                    <field name="full_width" invisible="1"/>
                    <div class="o_knowledge_editor">
                        <field name="body" widget="knowledge_html"/>
                    </div>
                </sheet>
            </form>`,
        list: /* xml */ `<list><field name="display_name"/></list>`,
    };

    get_sidebar_articles() {
        return { articles: [], favorite_ids: [] };
    }

    has_access = () => true;
}
