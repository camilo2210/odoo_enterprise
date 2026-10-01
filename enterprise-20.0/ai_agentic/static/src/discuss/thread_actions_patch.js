import { registerThreadAction } from "@mail/core/common/thread_actions";

import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

import { aiChatsActions } from "@ai/discuss/thread_actions_patch";
import { AiAgentActionPanel } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_action_panel";

aiChatsActions.push("configure-ai-agent");

registerThreadAction("configure-ai-agent", {
    actionPanelComponent: AiAgentActionPanel,
    actionPanelComponentProps: ({ channel }) => ({ agent: channel.ai_agent_id }),
    condition: ({ channel, owner, store }) =>
        channel?.isAiChat &&
        !!channel.ai_agent_id &&
        user.isAdmin &&
        owner.isDiscussContent &&
        (!store.discuss.scopedAiAgentId || store.env.services.ui.isSmall),
    icon: "settings",
    name: _t("Agent configuration"),
    sequenceGroup: 30,
});
