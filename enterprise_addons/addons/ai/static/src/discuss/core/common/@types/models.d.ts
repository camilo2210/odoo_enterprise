declare module "models" {
    import { AiAgent as AiAgentClass } from "@ai/discuss/core/common/ai_agent_model";
    import { AiComposer as AiComposerClass } from "@ai/discuss/core/common/ai_composer_model";
    import { AiSession as AiSessionClass } from "@ai/discuss/core/common/ai_session_model";
    import { AIPromptButton as AIPromptButtonClass } from "@ai/discuss/core/common/ai_prompt_model";

    export interface AiAgent extends AiAgentClass {}
    export interface AiComposer extends AiComposerClass {}
    export interface AiSession extends AiSessionClass {}
    export interface AIPromptButton extends AIPromptButtonClass {}

    export interface ChannelMember {
        isAiAgent: Readonly<boolean>;
        isAiResponding: boolean;
    }
    export interface DiscussChannel {
        ai_agent_id: AiAgent;
        ai_prompt_buttons: AIPromptButton[];
        ai_session_ids: AiSession[];
        aiInputSession: AiSession;
        aiRootSession: AiSession;
        aiChatSource: number|undefined;
        aiSpecialActions: Object|undefined;
        are_prompts_from_local_storage: boolean;
        disabledActions: Object|undefined;
        fromShopExtraImage: boolean|undefined;
        isAiGenerating: boolean;
        isAiSubmitting: boolean;
        localStoragePrompts: string|undefined;
        serializedPrompts: string|undefined;
        suggestedAiChannel: DiscussChannel;
        targetRecord: Object|undefined;
        textSelection: Object|undefined;
    }
    export interface ResPartner {
        agent_ids: AiAgent[];
    }
    export interface Store {
        "ai.agent": StaticMailRecord<AiAgent, typeof AiAgentClass>;
        "ai.composer": StaticMailRecord<AiComposer, typeof AiComposerClass>;
        "ai.prompt.button": StaticMailRecord<AIPromptButton, typeof AIPromptButtonClass>;
        "ai.session": StaticMailRecord<AiSession, typeof AiSessionClass>;
        aiInsertButtonTarget: number|false|undefined;
    }
    export interface Thread {
        ai_agent_id: AiAgent;
    }

    export interface Models {
        "ai.agent": AiAgent;
        "ai.composer": AiComposer;
        "ai.prompt.button": AIPromptButton;
        "ai.session": AiSession;
    }
}
