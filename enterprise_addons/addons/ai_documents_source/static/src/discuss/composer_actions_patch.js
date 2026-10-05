import { ComposerAction } from "@mail/core/common/composer_actions";
import { patch } from "@web/core/utils/patch";

patch(ComposerAction.prototype, {
    _getAiComposerActions() {
        return [...super._getAiComposerActions(), "add-documents"];
    },
});
