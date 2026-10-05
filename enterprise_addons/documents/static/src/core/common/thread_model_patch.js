import { Thread } from "@mail/core/common/thread_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Thread} */
const threadPatch = {
    setup() {
        super.setup(...arguments);
        /** @type {boolean|undefined} whether the thread model inherits documents.mixin */
        this.is_documents_mixin = undefined;
    },
};
patch(Thread.prototype, threadPatch);
