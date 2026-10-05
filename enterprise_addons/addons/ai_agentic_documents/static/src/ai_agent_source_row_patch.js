import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SOURCE_ICON_CONFIGS } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_source_icons";
import { AiAgentSourceRow } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_source_row";

SOURCE_ICON_CONFIGS.document = () => ({
    type: "image",
    src: "/ai_agentic_documents/static/img/icon.png",
    title: _t("Documents"),
});

patch(AiAgentSourceRow.prototype, {
    sourcesCountLabel() {
        if (this.record.data.type === "document" && this.record.data.is_folder) {
            const count = this.record.data.file_sources_count || 0;
            return `${count} ${count === 1 ? _t("Document") : _t("Documents")}`;
        }
        return super.sourcesCountLabel();
    },
});
