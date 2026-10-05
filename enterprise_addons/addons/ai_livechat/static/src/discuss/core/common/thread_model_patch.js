import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

patch(Thread.prototype, {
    get aiFromFrontend() {
        return session.is_frontend || session.livechatData;
    },
});
