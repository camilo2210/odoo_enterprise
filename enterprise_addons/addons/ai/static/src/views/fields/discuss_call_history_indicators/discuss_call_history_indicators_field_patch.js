import {
    DiscussCallHistoryIndicatorsField,
    discussCallHistoryIndicatorsField,
} from "@mail/views/fields/discuss_call_history_indicators/discuss_call_history_indicators_field";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

discussCallHistoryIndicatorsField.fieldDependencies.push({
    name: "has_transcript",
    type: "boolean",
});

patch(DiscussCallHistoryIndicatorsField.prototype, {
    icons() {
        const icons = super.icons();
        if (!this.props.record.data.has_transcript) {
            return icons;
        }
        return [...icons, { label: _t("Transcript"), name: "subtitles" }];
    },
});
