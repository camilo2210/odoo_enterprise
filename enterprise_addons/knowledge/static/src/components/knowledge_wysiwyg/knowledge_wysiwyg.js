import { proxy } from "@odoo/owl";
import { Wysiwyg } from "@html_editor/wysiwyg";
import { isEmptyBlock } from "@html_editor/utils/dom_info";
import { WysiwygArticleHelper } from "@knowledge/components/wysiwyg_article_helper/wysiwyg_article_helper";
import { _t } from "@web/core/l10n/translation";

export class KnowledgeWysiwyg extends Wysiwyg {
    static template = "knowledge.KnowledgeWysiwyg";
    static components = {
        ...Wysiwyg.components,
        WysiwygArticleHelper,
    };

    setup() {
        super.setup();
        this.articleHelperState = proxy({
            isVisible: false,
        });
    }

    /** @override */
    getEditorConfig() {
        const config = super.getEditorConfig();
        return {
            ...config,
            placeholder: _t("New Article"),
            onChange: () => {
                this.articleHelperState.isVisible = isEmptyBlock(this.editor.editable);
                config.onChange?.();
            },
            onEditorReady: () => {
                this.articleHelperState.isVisible = isEmptyBlock(this.editor.editable);
            },
        };
    }
}
