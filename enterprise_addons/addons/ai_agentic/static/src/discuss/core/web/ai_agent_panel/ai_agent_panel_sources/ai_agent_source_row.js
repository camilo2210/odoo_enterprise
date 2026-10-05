import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { SOURCE_ICON_CONFIGS, STATUS_BADGE_CLASS } from "./ai_agent_source_icons";
import { AiAgentSourceFolderTreePlugin } from "./ai_agent_source_folder_tree_plugin";

import { Component, t, useProps, usePlugin } from "@odoo/owl";

export class AiAgentSourceRow extends Component {
    static template = "ai_agentic.AiAgentSourceRow";
    static components = { AiAgentSourceRow, Dropdown, DropdownItem };

    setup() {
        this.props = useProps({
            record: t.any(),
            isNested: t.boolean().optional(),
        });
        this.orm = useService("orm");
        this.action = useService("action");
        this.sourcesFolderTree = usePlugin(AiAgentSourceFolderTreePlugin);
    }

    get record() {
        return this.props.record;
    }

    get isUnfolded() {
        return this.sourcesFolderTree.unfoldedIds().has(this.record.resId);
    }

    childRecords() {
        return this.sourcesFolderTree.childrenOf(this.record.resId);
    }

    sourceIconConfig() {
        const iconConfig = SOURCE_ICON_CONFIGS[this.record.data.type];
        return (iconConfig || SOURCE_ICON_CONFIGS.default)(this.record);
    }

    sourcesCountLabel() {
        return "";
    }

    statusBadgeClass() {
        return STATUS_BADGE_CLASS[this.record.data.status] || "text-bg-secondary";
    }

    statusErrorTooltip() {
        const { status, error_details } = this.record.data;
        return ["failed", "incomplete"].includes(status) ? error_details : "";
    }

    canOpenSource() {
        const { file_sources_count, is_folder, status, user_has_access } = this.record.data;
        return (is_folder && file_sources_count > 0) || (status === "indexed" && user_has_access);
    }

    canRetryOrReprocess() {
        const { status, type } = this.record.data;
        return (
            status === "failed" ||
            status === "incomplete" ||
            (status === "indexed" && type !== "binary")
        );
    }

    canToggleActive() {
        const { status } = this.record.data;
        return status !== "processing" && status !== "failed";
    }

    retryOrReprocessLabel() {
        return this.record.data.status === "indexed" ? _t("Reprocess") : _t("Retry");
    }

    toggleActiveLabel() {
        return this.record.data.is_active ? _t("Disable") : _t("Enable");
    }

    async onClickSource() {
        if (!this.canOpenSource()) {
            return;
        }
        if (this.record.data.is_folder) {
            await this.sourcesFolderTree.toggleFolder(this.record);
            return;
        }
        const action = await this.orm.call("ai.agent.source", "action_access_source", [
            [this.record.resId],
        ]);
        if (action) {
            await this.action.doAction(action);
        }
    }

    async onClickToggleActive() {
        const is_active = !this.record.data.is_active;
        await this.orm.write("ai.agent.source", [this.record.resId], { is_active });
        this.sourcesFolderTree.patchRecord(this.record.resId, { is_active });
    }

    async onClickRetryOrReprocess() {
        const method =
            this.record.data.status === "indexed"
                ? "action_reprocess_index"
                : "action_retry_failed_source";
        await this.orm.call("ai.agent.source", method, [[this.record.resId]]);
        this.sourcesFolderTree.patchRecord(this.record.resId, { status: "processing" });
    }

    async onClickRemoveSource() {
        await this.orm.unlink("ai.agent.source", [this.record.resId]);
        this.sourcesFolderTree.removeRecord(this.record.resId);
    }
}
