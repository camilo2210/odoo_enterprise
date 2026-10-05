import { Composer } from "@mail/core/common/composer_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Composer} */
const composerPatch = {
    setup() {
        super.setup();
        this.whatsappThreadDisabled = false;
    },
};
patch(Composer.prototype, composerPatch);
