import { AiPrompt, AiPromptDialog } from "@ai/ai_prompt/ai_prompt";
import { computed, signal } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { FieldProperties } from "@web_studio/client_action/view_editor/interactive_editor/properties/field_properties/field_properties";
import { _t } from "@web/core/l10n/translation";
import { KeepLast, Mutex } from "@web/core/utils/concurrency";

Object.assign(FieldProperties.components, { AiPrompt });

// todo: ideally should apply them by default for ai fields
const aiWidgetForFieldType = {
    char: "ai_char",
    text: "ai_text",
    html: "ai_html",
    integer: "ai_integer",
    float: "ai_float",
    monetary: "ai_monetary",
    date: "ai_date",
    datetime: "ai_datetime",
    boolean: "ai_boolean",
    selection: "ai_selection",
    many2one: "ai_many2one",
    many2many: "ai_many2many_tags",
};

patch(FieldProperties.prototype, {
    setup() {
        super.setup();
        this.tempAiValues = signal.Object({});
        this.aiValues = computed(() => {
            const field = this.props.node.field;
            const tempAiValues = this.tempAiValues();
            return {
                ai: tempAiValues.ai ?? (field.ai || field.ai === ""),
                system_prompt: tempAiValues.system_prompt ?? (field.ai || ""),
            };
        });
        this.editAiValuesMutex = new Mutex();
        this.keepLast = new KeepLast();
        this.hasAi = computed(() => !!this.aiValues().ai);
        this.aiSupported = computed(() => true);
        this.hasPrompt = computed(() => !!this.aiValues().system_prompt);
    },

    async onChangeAi(value) {
        const field = this.props.node.field;
        const prevWidget = this.props.node.attrs.widget || "";
        this.updateFieldAIValues({ ai: value });
        await this.keepLast.add(this.editAiValuesMutex.getUnlockedDef());
        const nextWidget = this.aiValues().ai ? aiWidgetForFieldType[field.type] : "";
        if (prevWidget !== nextWidget) {
            this.onChangeAttribute(nextWidget, "widget");
        }
    },

    async updateFieldAIValues(values) {
        const field = this.props.node.field;
        await this.editAiValuesMutex.exec(async () => {
            Object.assign(this.tempAiValues(), values);
            const aiValues = this.aiValues();
            try {
                await rpc("/web_studio/edit_field", {
                    model_name: this.env.viewEditorModel.resModel,
                    field_name: field.name,
                    values: values,
                });
                field.ai = aiValues.ai && aiValues.system_prompt;
            } finally {
                this.tempAiValues.set({});
            }
        });
    },

    updateSystemPrompt(value) {
        return this.updateFieldAIValues({ system_prompt: value });
    },

    onSystemPromptClick() {
        if (!this.aiSupported()) {
            return;
        }
        this.dialog.add(AiPromptDialog, {
            aiPromptProps: {
                comodel: this.comodel,
                domain: this.props.node.attrs.domain || "",
                model: this.env.viewEditorModel.resModel,
                prompt: this.aiValues().system_prompt,
                readonly: false,
                aiFieldPath: this.props.node.field.name,
                placeholder: _t("Describe how to compute this field, or type '/' for commands..."),
            },
            confirm: (newPrompt) => this.updateSystemPrompt(newPrompt),
        });
    },

    get comodel() {
        if (["many2one", "many2many"].includes(this.props.node.field.type)) {
            return this.props.node.field.relation;
        }
        return undefined;
    },
});
