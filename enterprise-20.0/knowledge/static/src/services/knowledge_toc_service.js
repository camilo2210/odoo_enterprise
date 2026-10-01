import { registry } from "@web/core/registry";
import { effect, proxy } from "@odoo/owl";

export const knowledgeTocService = {
    start() {
        this.tocState = proxy({
            articleId: undefined,
            tocManager: undefined,
        });
        let previousArticleId;
        const disposeEffect = effect(() => {
            if (previousArticleId !== this.tocState.articleId) {
                this.resetForArticleId();
                previousArticleId = this.tocState.articleId;
            }
        });
        registry.category("services").addEventListener("CLEANUP", disposeEffect, { once: true });
        return {
            setArticleId: this.setArticleId.bind(this),
            getTocState: this.getTocState.bind(this),
        };
    },
    getTocState() {
        return this.tocState;
    },
    setArticleId(articleId) {
        if (articleId !== this.tocState.articleId) {
            this.tocState.articleId = articleId;
        }
    },
    resetForArticleId() {
        if (this.tocState.tocManager) {
            this.tocState.tocManager.structure.isNew = true;
            this.tocState.tocManager.structure.headings = [];
        }
    },
};

registry.category("services").add("knowledge.toc", knowledgeTocService);
