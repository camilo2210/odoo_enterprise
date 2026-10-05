import { Component } from "@odoo/owl";

export class ViewPlaceholderComponent extends Component {
    static template = "website_knowledge.ViewPlaceholder";

    setup() {
        this.url = `/knowledge/article/${this.env.articleId}`;
    }
}

export const viewPlaceholderEmbedding = {
    name: "view",
    Component: ViewPlaceholderComponent,
};
