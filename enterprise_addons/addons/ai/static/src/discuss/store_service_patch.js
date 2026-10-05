import { Store } from "@mail/core/common/store_service";
import { patch } from "@web/core/utils/patch";

patch(Store.prototype, {
    /**
     * @override
     */
    tabToThreadType(tab) {
        const threadTypes = super.tabToThreadType(tab);
        if (tab === "aiChat") {
            threadTypes.push("ai_chat");
        }
        return threadTypes;
    },
});
