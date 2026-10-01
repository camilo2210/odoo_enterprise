import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {number|undefined} */
        this.articleId = undefined;
    },
    /** @override */
    open() {
        if (this.model !== "knowledge.article.thread") {
            return super.open(...arguments);
        }
        this.store.env.services.orm
            .read("knowledge.article.thread", [this.id], ["article_id"], { load: false })
            .then(([articleThreadData]) => {
                this.store.env.services.action.doAction(
                    "knowledge.ir_actions_server_knowledge_home_page",
                    {
                        stackPosition: "replaceCurrentAction",
                        additionalContext: {
                            res_id: articleThreadData["article_id"],
                        },
                    }
                );
            });
        return true;
    },
});
