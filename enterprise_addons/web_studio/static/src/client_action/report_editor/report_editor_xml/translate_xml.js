import { rpc } from "@web/core/network/rpc";
import {
    TranslationButton as _TranslationButton,
    TranslateModel as _TranslateModel,
} from "@web/views/fields/translation/translation";

class TranslateModel extends _TranslateModel {
    setup() {
        super.setup();
        this.get_translation_key.use(
            (attrs) => `${attrs["data-oe-id"]}//${attrs["data-oe-translation-source-sha"]}`
        );
    }
    _load({ resId, field, lang }) {
        return rpc("/web_studio/get_view_translations", {
            view_id: resId(),
            field_name: field().name,
            target_lang: lang(),
        });
    }
    _save({ resId, field, lang, changes }) {
        return rpc("/web_studio/save_view_translations", {
            view_id: resId(),
            field_name: field().name,
            changes,
            target_lang: lang?.(),
        });
    }

    _getChanges() {
        const changes = {};
        for (const [lang, hashes] of Object.entries(this.changesSet())) {
            for (const [key, value] of Object.entries(hashes)) {
                const [viewId, hash] = key.split("//");
                changes[viewId] ??= {};
                changes[viewId][lang] ??= {};
                changes[viewId][lang][hash] = value;
            }
        }
        return changes;
    }
}

export class TranslationButton extends _TranslationButton {
    static Plugins = [TranslateModel];
}
