import { Voip } from "@voip/core/web/voip_service";

import { patch } from "@web/core/utils/patch";

patch(Voip.prototype, {
    get transcriptionEnabled() {
        return this.config.transcriptionPolicy === "always";
    },
});
