import { KnowledgeMessage } from "@knowledge/comments/knowledge_message";
import { Thread } from "@mail/core/common/thread";

export class KnowledgeThread extends Thread {
    static components = { ...Thread.components, Message: KnowledgeMessage };
}
