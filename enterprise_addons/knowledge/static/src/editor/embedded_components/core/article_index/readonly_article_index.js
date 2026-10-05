import { Component, useProps, t } from "@odoo/owl";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";

export class ReadonlyEmbeddedArticleIndexComponent extends Component {
    props = useProps({
        articles: t.array().optional([]),
        showAllChildren: t.boolean().optional(true),
    });
    static template = "knowledge.ReadonlyEmbeddedArticleIndex";

    /** @param {integer} articleId */
    openArticle(articleId) {
        if (this.env.openArticle) {
            this.env.openArticle(articleId);
        }
    }
}

export const readonlyArticleIndexEmbedding = {
    name: "articleIndex",
    Component: ReadonlyEmbeddedArticleIndexComponent,
    getProps: (host) => {
        return {
            ...getEmbeddedProps(host),
        };
    },
};
