import { Call } from "@voip/core/common/call_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Call} */
const callPatch = {
    setup() {
        super.setup(...arguments);
        /** @type {boolean|undefined} */
        this.has_transcript = undefined;
        /** @type {string|undefined} */
        this.transcription_state = undefined;
    },
};
patch(Call.prototype, callPatch);
