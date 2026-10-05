import { SUGGESTION_DELIMITERS } from "@mail/core/common/suggestion_hook";
import { SuggestionService } from "@mail/core/common/suggestion_service";

import { patch } from "@web/core/utils/patch";

patch(SuggestionService.prototype, {
    /** @override */
    searchSuggestions({ delimiter, term }, { thread } = {}) {
        if (
            ["ai_composer", "ai_chat"].includes(thread?.channel?.channel_type) &&
            delimiter === SUGGESTION_DELIMITERS.PARTNER
        ) {
            return {
                type: undefined,
                suggestions: [],
            };
        }
        return super.searchSuggestions(...arguments);
    },
});
