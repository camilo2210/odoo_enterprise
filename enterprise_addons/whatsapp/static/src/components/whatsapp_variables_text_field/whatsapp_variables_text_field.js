import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { TextField, textField } from "@web/views/fields/text/text_field";
import { Tooltip } from "@web/core/tooltip/tooltip";
import { usePopover } from "@web/core/popover/popover_hook";

import { signal } from "@odoo/owl";

export class WhatsappVariablesTextField extends TextField {
    static template = "whatsapp.WhatsappVariablesTextField";
    static components = { ...TextField.components };
    variablesButtonRef = signal.ref();

    setup() {
        super.setup();
        this.popover = usePopover(Tooltip, { animation: false, position: "left" });
    }

    _onClickAddVariables() {
        const originalContent = this.textareaRef().value;
        const start = this.textareaRef().selectionStart;
        const end = this.textareaRef().selectionEnd;

        const matches = Array.from(originalContent.matchAll(/{{([^{}]*)}}/g));
        const variableType = this.props.record.data.variable_type;

        if (matches.length >= 10) {
            // Show tooltip
            this.popover.open(this.variablesButtonRef(), {
                tooltip: _t("You can set a maximum of 10 variables."),
            });
            browser.setTimeout(this.popover.close, 2600);
            return;
        }

        let newVariable = "{{}}";
        if (variableType === "positional") {
            const numberedMatches = matches.map(m => m[1]).filter(s => /^\d+$/.test(s)).map(Number);
            const nextVariable = Math.max(...numberedMatches, 0) + 1;
            newVariable = `{{${nextVariable}}}`;
        }
        const separator = originalContent.slice(0, start) ? " " : "";
        this.textareaRef().value =
            originalContent.slice(0, start) +
            separator +
            newVariable +
            originalContent.slice(end, originalContent.length);
        // Trigger onInput from input_field hook to set field as dirty
        this.textareaRef().dispatchEvent(new InputEvent("input"));
        // Change event serves to both commit the changes in input_field and trigger onchange for some fields
        this.textareaRef().dispatchEvent(new Event("change"));
        this.textareaRef().focus();
        const cursorOffset = variableType === "named" ? 2 : newVariable.length;
        const newCursorPos = start + separator.length + cursorOffset;
        this.textareaRef().setSelectionRange(newCursorPos, newCursorPos);
    }
}

export const whatsappVariablesTextField = {
    ...textField,
    component: WhatsappVariablesTextField,
    additionalClasses: [...(textField.additionalClasses || []), "o_field_text"],
};

registry.category("fields").add("whatsapp_text_variables", whatsappVariablesTextField);
