import { Record } from "@web/model/relational_model/record";
import { useAutofocus } from "@web/core/utils/hooks";
import { useInputField } from "@web/views/fields/input_field_hook";

import { Component, signal, t, useProps } from "@odoo/owl";

export class AiAgentSystemPromptEditor extends Component {
    static template = "ai_agentic.AiAgentSystemPromptEditor";

    props = useProps({
        record: t.instanceOf(Record),
        placeholder: t.string(),
    });

    isEditing = signal(false);
    textareaRef = signal.ref();

    setup() {
        useAutofocus({ ref: this.textareaRef });
        useInputField({
            ref: this.textareaRef,
            fieldName: "system_prompt",
            getValue: () => this.props.record.data.system_prompt || "",
        });
    }

    get isEmpty() {
        return !(this.props.record.data.system_prompt || "").trim();
    }

    startEditing() {
        this.isEditing.set(true);
    }

    async stopEditing() {
        await this.props.record.isDirty(); // forces the pending edit to commit first
        this.isEditing.set(false);
    }
}
