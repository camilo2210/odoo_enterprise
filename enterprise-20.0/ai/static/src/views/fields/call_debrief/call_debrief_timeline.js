import { t } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

import { CallDebriefTimeline, callDebriefTimelineProps } from "@mail/views/fields/call_debrief/call_debrief_timeline";

Object.assign(callDebriefTimelineProps, {
    transcriptLines: t.array().optional(),
});

patch(CallDebriefTimeline.prototype, {
    _stylePositionTranscriptMarker(line) {
        if (!this.props.totalDuration) {
            return "left: 0%;";
        }
        return `left: ${(line.startSecRelToCall / this.props.totalDuration) * 100}%;`;
    },
});
