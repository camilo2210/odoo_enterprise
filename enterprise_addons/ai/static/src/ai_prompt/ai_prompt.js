import { AI_FIELD_SELECTOR, AIFieldSelectorPlugin } from "@ai/ai_prompt/ai_field_selector_plugin";
import {
    AI_RECORD_SELECTOR,
    AIRecordsSelectorPlugin,
} from "@ai/ai_prompt/ai_records_selector_plugin";
import { FeffPlugin } from "@html_editor/main/feff_plugin";
import { HintPlugin } from "@html_editor/main/hint_plugin";
import { PlaceholderPlugin } from "@html_editor/main/placeholder_plugin";
import { PowerboxPlugin } from "@html_editor/main/powerbox/powerbox_plugin";
import { SearchPowerboxPlugin } from "@html_editor/main/powerbox/search_powerbox_plugin";
import { CORE_PLUGINS } from "@html_editor/plugin_sets";
import { childNodeIndex } from "@html_editor/utils/position";
import { withSequence } from "@html_editor/utils/resource";
import { Wysiwyg } from "@html_editor/wysiwyg";
import { Dialog } from "@web/core/dialog/dialog";
import { localization } from "@web/core/l10n/localization";
import { isHtmlEmpty } from "@web/core/utils/html";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

import { Component, markup, proxy, onPatched, t, usePlugin, useProps } from "@odoo/owl";

export class AiPrompt extends Component {
    static template = "ai.AiPrompt";
    static components = { Wysiwyg };

    props = useProps({
        comodel: t.string().optional(),
        domain: t.string().optional(),
        model: t.string().optional(),
        onChange: t.function().optional(),
        placeholder: t.string().optional(),
        prompt: t.string(),
        readonly: t.boolean().optional(),
        aiFieldPath: t.string().optional(),
        missingRecordsWarning: t.string().optional(),
        updatePrompt: t.function().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.state = proxy({
            key: 0,
            hasRecords: this.props.prompt.includes("data-ai-record"),
        });

        this.lastValue = this.props.prompt;
        let prev = { ...this.props };

        onPatched(() => {
            const { prompt, comodel, domain } = this.props;
            const promptChanged = `${prompt || ""}` !== `${prev.prompt || ""}`;
            const configChanged = comodel !== prev.comodel || domain !== prev.domain;
            prev = { prompt, comodel, domain };

            if (promptChanged) {
                if (`${prompt || ""}` === `${this.lastValue || ""}`) {
                    return;
                }
                this.lastValue = prompt;
            } else if (!configChanged) {
                return;
            }
            this.state.key++;
        });
    }

    get content() {
        const elContent = this.editor.getElContent();
        if (isHtmlEmpty(elContent.innerText)) {
            return "";
        }
        return elContent.innerHTML;
    }

    get hasRecords() {
        return Boolean(this.editor.getElContent().querySelector(AI_RECORD_SELECTOR));
    }

    get missingRecordsWarning() {
        return this.props.comodel && !this.state.hasRecords && this.props.missingRecordsWarning;
    }

    get value() {
        return markup(this.props.prompt || "<p><br></p>");
    }

    getConfig() {
        return {
            content: this.value,
            debug: this.debugMode.isActive(),
            direction: localization.direction || "ltr",
            aiFieldPath: this.props.aiFieldPath,
            fieldSelectorResModel: this.props.model,
            getRecordInfo: () => {
                const { resModel, resId } = this.props.record;
                return { resModel, resId };
            },
            onChange: () => this.onChange(),
            onEditorReady: () => (this.state.hasRecords = this.hasRecords),
            placeholder: this.props.placeholder,
            Plugins: [
                ...CORE_PLUGINS,
                AIFieldSelectorPlugin,
                AIRecordsSelectorPlugin,
                FeffPlugin,
                HintPlugin,
                PlaceholderPlugin,
                PowerboxPlugin,
                SearchPowerboxPlugin,
            ],
            baseContainers: ["DIV"],
            recordsSelectorDomain: this.props.domain,
            recordsSelectorResModel: this.props.comodel,
            // small hack to continue to show the placeholder when the widget is focused but empty
            resources: {
                hints: [
                    withSequence(20, {
                        selector: ".odoo-editor-editable > p:only-child",
                        text: this.props.placeholder,
                    }),
                ],
            },
        };
    }

    onBlur() {
        const content = this.content;
        if (content !== this.lastValue) {
            this.props.updatePrompt(this.content);
            this.lastValue = content;
        }
    }

    onChange() {
        this.state.hasRecords = this.hasRecords;
        this.props.onChange?.();
    }

    onClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const target = ev.target?.closest(`${AI_FIELD_SELECTOR}, ${AI_RECORD_SELECTOR}`);
        if (!target) {
            return;
        }
        // select the target to remove it when we will insert
        this.editor.shared.selection.setSelection({
            anchorNode: target.parentElement,
            anchorOffset: childNodeIndex(target),
            focusOffset: childNodeIndex(target) + 1,
        });
        if (target.matches(AI_FIELD_SELECTOR)) {
            this.editor.shared.AIFieldSelector.open([target.dataset.aiField]);
        } else if (this.props.comodel) {
            this.editor.shared.AIRecordsSelector.open([Number(target.dataset.aiRecordId)]);
        }
    }

    onEditorLoad(editor) {
        this.editor = editor;
    }
}

export class AiPromptDialog extends Component {
    static template = "ai.AiPromptDialog";
    static components = { Dialog, AiPrompt };

    props = useProps({
        aiPromptProps: t.object(),
        close: t.function(),
        confirm: t.function(),
    });

    setup() {
        super.setup();
        this.confirmVals = { prompt: this.props.aiPromptProps.prompt };
    }

    get aiPromptProps() {
        return {
            ...this.props.aiPromptProps,
            updatePrompt: (prompt) => (this.confirmVals.prompt = prompt),
        };
    }

    confirm() {
        this.props.confirm(this.confirmVals.prompt);
        this.props.close();
    }
}
