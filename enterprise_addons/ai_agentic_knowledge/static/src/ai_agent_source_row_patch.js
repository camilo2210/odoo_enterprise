import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SOURCE_ICON_CONFIGS } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_source_icons";
import { AiAgentSourceRow } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_source_row";

SOURCE_ICON_CONFIGS.knowledge_article = () => ({
    type: "image",
    src: "/ai_agentic_knowledge/static/img/icon.png",
    title: _t("Knowledge Article"),
});

patch(AiAgentSourceRow.prototype, {
    sourcesCountLabel() {
        if (this.record.data.type === "knowledge_article") {
            const count = this.record.data.file_sources_count || 0;
            const childrenCount = count - 1;
            if (childrenCount <= 0) {
                return "";
            }
            return `+${childrenCount} ${childrenCount === 1 ? _t("Article") : _t("Articles")}`;
        }
        return super.sourcesCountLabel();
    },
});
