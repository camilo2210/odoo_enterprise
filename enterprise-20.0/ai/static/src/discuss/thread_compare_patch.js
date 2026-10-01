import { threadCompareRegistry } from "@mail/core/common/thread_compare";
import { compareDatetime } from "@mail/utils/common/misc";

threadCompareRegistry.add(
    "ai.ai_chat-last-activity",
    /**
     * AI chats are sorted on a single timeline: most recent message time, or
     * (for chats with nothing said yet) creation time instead.
     *
     * @param {import("models").Thread} thread1
     * @param {import("models").Thread} thread2
     */
    (thread1, thread2) => {
        if (!thread1.channel?.isAiChat || !thread2.channel?.isAiChat) {
            return undefined;
        }
        const aTime = thread1.newestPersistentOfAllMessage?.datetime ?? thread1.channel.create_date;
        const bTime = thread2.newestPersistentOfAllMessage?.datetime ?? thread2.channel.create_date;
        const res = compareDatetime(bTime, aTime);
        if (res !== 0) {
            return res;
        }
    },
    { sequence: 20 }
);
