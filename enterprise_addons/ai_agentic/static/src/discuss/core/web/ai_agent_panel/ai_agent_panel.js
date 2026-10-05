import { Record } from "@web/model/record";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { extractFieldsFromArchInfo } from "@web/model/relational_model/utils";
import { CharField } from "@web/views/fields/char/char_field";
import { Field } from "@web/views/fields/field";
import { ImageField } from "@web/views/fields/image/image_field";
import { FormArchParser } from "@web/views/form/form_arch_parser";
import { _t } from "@web/core/l10n/translation";
import { parseXML } from "@web/core/utils/xml";
import { useSetupAction } from "@web/search/action_hook";
import { useService } from "@web/core/utils/hooks";
import { pick } from "@web/core/utils/objects";
import { useDebounced } from "@web/core/utils/timing";
import { AiAgentSystemPromptEditor } from "@ai_agentic/components/ai_agent_system_prompt_editor/ai_agent_system_prompt_editor";
import { AiAgentPanelNativeSkills } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_skills/ai_agent_panel_native_skills";
import "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_skills/ai_agent_panel_skills";
import "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_sources/ai_agent_panel_sources";
import "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel_triggers/ai_agent_panel_triggers";

import { browser } from "@web/core/browser/browser";

import { Component, onWillStart, proxy, t, useProps } from "@odoo/owl";

const AI_AGENT_MODEL = "ai.agent";
const AI_AGENT_PANEL_VIEW_REF = "ai_agentic.ai_agent_view_form";
// Fields shown as the channel name/subtitle (Need to be in sync).
const AI_AGENT_DISPLAY_FIELD_NAMES = ["name", "subtitle"];
const TABS = [
    { id: "instructions", label: _t("Instructions") },
    { id: "skills", label: _t("Skills") },
    { id: "knowledge", label: _t("Knowledge") },
    { id: "triggers", label: _t("Triggers") },
];
const DEFAULT_TAB_ID = TABS[0].id;
const ACTIVE_TAB_IDS_KEY = "ai_agentic.AiAgentPanel.activeTabIds";

function readActiveTabIds() {
    try {
        return JSON.parse(browser.sessionStorage.getItem(ACTIVE_TAB_IDS_KEY)) ?? {};
    } catch {
        return {};
    }
}

function getFieldNodesByName(archInfo) {
    return Object.fromEntries(
        Object.values(archInfo.fieldNodes).map((fieldNode) => [fieldNode.name, fieldNode])
    );
}

export class AiAgentPanel extends Component {
    static components = {
        AiAgentSystemPromptEditor,
        AiAgentPanelNativeSkills,
        CharField,
        Dropdown,
        DropdownItem,
        Field,
        ImageField,
        Record,
    };
    static template = "ai_agentic.AiAgentPanel";
    tabs = TABS;

    setup() {
        super.setup();
        this.props = useProps({
            agent: t.any(),
            showAgentActions: t.boolean().optional(),
        });
        this.viewService = useService("view");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        onWillStart(() => this.loadPanelView());
        this.debouncedSaveAgentChanges = useDebounced(() => this.flushAgentChanges(), 500);
        this.recordHooks = {
            onRecordChanged: (record) => {
                this.record = record;
                this.debouncedSaveAgentChanges();
            },
        };
        // Saves before leaving the action: a debounced save can't rely on
        // execBeforeUnmount, its RPC is aborted before onWillDestroy runs.
        useSetupAction({ beforeLeave: () => this.flushAgentChanges() });
        this.state = proxy({ activeTabIds: readActiveTabIds() });
    }

    /** Single choke point for both the debounce and beforeLeave. */
    async flushAgentChanges() {
        this.debouncedSaveAgentChanges.cancel();
        if (this.record) {
            await this.saveAgentChanges(this.record);
        }
    }

    get activeTabId() {
        const tabId = this.state.activeTabIds[this.agent?.id];
        return TABS.some((tab) => tab.id === tabId) ? tabId : DEFAULT_TAB_ID;
    }

    isActiveTab(id) {
        return this.activeTabId === id;
    }

    setActiveTab(id) {
        this.state.activeTabIds[this.agent.id] = id;
        browser.sessionStorage.setItem(ACTIVE_TAB_IDS_KEY, JSON.stringify(this.state.activeTabIds));
    }

    async loadPanelView() {
        const { fields, relatedModels, views } = await this.viewService.loadViews({
            context: { form_view_ref: AI_AGENT_PANEL_VIEW_REF },
            resModel: AI_AGENT_MODEL,
            views: [[false, "form"]],
        });
        const parser = new FormArchParser();
        const arch = views.form.arch;

        this.agentArchInfo = parser.parse(parseXML(arch), relatedModels, AI_AGENT_MODEL);
        const { activeFields } = extractFieldsFromArchInfo(this.agentArchInfo, fields);
        if (!Object.keys(activeFields).length) {
            return;
        }

        this.agentFields = fields;
        this.agentActiveFields = activeFields;
        this.fieldNodes = getFieldNodesByName(this.agentArchInfo);
    }

    get agent() {
        return this.props.agent;
    }

    get resModel() {
        return AI_AGENT_MODEL;
    }

    archiveAgent(record) {
        this.dialog.add(ConfirmationDialog, {
            body: _t("Are you sure that you want to archive this agent?"),
            confirmLabel: _t("Archive"),
            confirm: async () => {
                await this.flushAgentChanges();
                await record.archive();
                await this.actionService.doAction("ai_agentic.ai_agent_action", {
                    clearBreadcrumbs: true,
                });
            },
            cancel: () => {},
        });
    }

    async unarchiveAgent(record) {
        await this.flushAgentChanges();
        await record.unarchive();
    }

    deleteAgent(record) {
        this.dialog.add(ConfirmationDialog, {
            body: _t("Are you sure that you want to delete this agent?"),
            confirmLabel: _t("Delete"),
            confirmClass: "btn-danger",
            confirm: async () => {
                if ((await record.delete()) !== false) {
                    this.agent?.delete();
                    await this.actionService.doAction("ai_agentic.ai_agent_action", {
                        clearBreadcrumbs: true,
                    });
                }
            },
            cancel: () => {},
        });
    }

    async saveAgentChanges(record) {
        if (
            (await record.isDirty()) &&
            (await record.checkValidity({ displayNotification: true })) &&
            (await record.save({ reload: false }))
        ) {
            this.agent?.update(pick(record.data, ...AI_AGENT_DISPLAY_FIELD_NAMES));
        }
    }
}
