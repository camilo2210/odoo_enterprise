import { History } from "@voip/softphone/history";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(History.prototype, {
    /**
     * @override
     * @param {import("models").Call} call
     * @returns {Object[]}
     */
    getSubtitleExtraIcons(call) {
        const icons = super.getSubtitleExtraIcons(call);
        if (call.transcription_state === "done") {
            icons.push({ name: "subtitles", title: _t("Transcript") });
        }
        return icons;
    },
});
