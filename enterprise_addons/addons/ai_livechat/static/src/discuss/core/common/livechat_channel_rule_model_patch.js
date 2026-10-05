import { LivechatChannelRule } from "@im_livechat/core/common/livechat_channel_rule_model";
import { fields } from "@mail/model/export";

import { patch } from "@web/core/utils/patch";

patch(LivechatChannelRule.prototype, {
    setup() {
        super.setup(...arguments);
        this.ai_agent_id = fields.One("ai.agent");
    },
});
