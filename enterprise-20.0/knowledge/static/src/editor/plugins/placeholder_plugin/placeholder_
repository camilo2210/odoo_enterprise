import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";

export class KnowledgePlaceholderPlugin extends Plugin {
    static id = "knowledgePlaceholder";
    /** @type {import("plugins").EditorResources} */
    resources = {
        ...(this.config.placeholder && {
            hints: [
                withSequence(1, {
                    selector: `.odoo-editor-editable > h1:only-child`,
                    text: this.config.placeholder,
                }),
            ],
            placeholder_hint_target_overrides: (el) => el.matches("h1"),
        }),
    };
}
