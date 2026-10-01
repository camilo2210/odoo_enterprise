import { knowledgeTopbar } from "@knowledge/components/topbar/topbar";
import { patch } from "@web/core/utils/patch";

patch(knowledgeTopbar, {
    fieldDependencies: [
        ...knowledgeTopbar.fieldDependencies,
        { name: "website_published", type: "boolean", readonly: false },
        { name: "article_url", type: "char" },
    ],
});
