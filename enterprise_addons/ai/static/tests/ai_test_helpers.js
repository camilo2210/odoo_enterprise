import { mailModels } from "@mail/../tests/mail_test_helpers";
import { AIAgent, AIAgentSource } from "./mock_server/mock_models/ai_agent";
import { Partner } from "./mock_server/mock_models/res_partner";
import { defineModels } from "@web/../tests/web_test_helpers";
import { AIComposer } from "./mock_server/mock_models/ai_composer";
import { AIPromptButton } from "./mock_server/mock_models/ai_prompt_button";
import { AISession } from "./mock_server/mock_models/ai_session";
import { DiscussChannel } from "./mock_server/mock_models/discuss_channel";

export function defineAIModels() {
    return defineModels(aiModels);
}

export function createAIChat(pyEnv, agentId) {
    const channelId = pyEnv["ai.agent"].browse(agentId)._create_ai_chat_channel();
    const sessionId = pyEnv["ai.session"].create({ agent_id: agentId, channel_id: channelId });
    return { channelId, sessionId };
}

export const aiModels = {
    ...mailModels,
    AIAgent,
    AIComposer,
    AIPromptButton,
    AISession,
    AIAgentSource,
    DiscussChannel,
    Partner,
};
