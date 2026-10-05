import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { patch } from "@web/core/utils/patch";

patch(DiscussChannel.prototype, {
    get allowCalls() {
        if (this.ai_agent_id) {
            return false;
        }
        return super.allowCalls;
    },
});
