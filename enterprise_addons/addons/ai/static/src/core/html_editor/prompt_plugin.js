import { _t } from "@web/core/l10n/translation";
import { Plugin } from "@html_editor/plugin";
import { DYNAMIC_FIELD_PLUGINS } from "@html_editor/backend/dynamic_field/dynamic_field_plugin";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";
import { htmlEscape } from "@odoo/owl";
import { parseHTML } from "@html_editor/utils/html";

export class PromptPlugin extends Plugin {
    static id = "prompt";
    static dependencies = ["dom", "history", "selection"];
    resources = {
        user_commands: [
            {
                id: "prompt",
                title: _t("Prompt"),
                description: _t("Insert an AI prompt"),
                icon: "flash_on",
                run: this.insertPrompt.bind(this),
                isAvailable: isHtmlContentSupported,
            },
        ],
        powerbox_items: [
            {
                commandId: "prompt",
                categoryId: "ai",
            },
        ],
    };

    insertPrompt() {
        const emojiHtml = `<i class="o_editor_banner_icon mb-3 fst-normal" data-oe-aria-label="${htmlEscape(
            _t("Prompt")
        )}">⚡</i>`;
        const bannerElement = parseHTML(
            this.document,
            `<div class="o_editor_prompt o_editor_banner user-select-none o-contenteditable-false lh-1 
                d-flex align-items-center alert alert-primary pb-0 pt-3 ps-3 pe-3" data-oe-role="status">
                ${emojiHtml}
                <div class="o_editor_prompt_content o_editor_banner_content o-contenteditable-true w-100 px-3">
                    <div><br></div>
                </div>
            </div>`
        ).childNodes[0];
        this.dependencies.dom.insert(bannerElement);
        this.dependencies.selection.setCursorEnd(
            bannerElement.querySelector(`.o_editor_prompt_content > div`)
        );
        this.dependencies.history.commit();
    }
}

DYNAMIC_FIELD_PLUGINS.push(PromptPlugin);
