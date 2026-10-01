import { WysiwygArticleHelper } from "@knowledge/components/wysiwyg_article_helper/wysiwyg_article_helper";

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

patch(WysiwygArticleHelper.prototype, {
    setup(){
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
    },
    async onGenerateArticleClick() {
        // remove the "default" h1 of the article, otherwise we'll insert into the h1
        const existingTitle = this.props.editor.document.querySelector("h1");
        if (existingTitle) {
            existingTitle.remove();
        }
        await this.props.editor.shared.chatgpt.openDialog({
            "callerComp": "html_field_knowledge",
            "channelTitle": _t("Knowledge Article Editor"),
        });
    }
});
