import SystrayAction from "@ai/web/systray_action";

import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(SystrayAction.prototype, {
    setup() {
        super.setup();
        this.store = useService("mail.store");
    },
    onClickLaunchAIChat() {
        this.store.discuss.clearScopedAiAgent();
        return super.onClickLaunchAIChat();
    },
});
