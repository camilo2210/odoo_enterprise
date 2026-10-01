import { VoipCallIndicatorsField } from "@voip/widgets/voip_call_indicators_field";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(VoipCallIndicatorsField.prototype, {
    get icons() {
        const icons = super.icons;
        if (this.props.record.data.has_transcript) {
            icons.push({
                label: _t("Transcript"),
                name: "subtitles",
                classes: "oi ms-1 text-muted",
            });
        }
        return icons;
    },
});
