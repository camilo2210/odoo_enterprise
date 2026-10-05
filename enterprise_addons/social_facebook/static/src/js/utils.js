const _FACEBOOK_REACTIONS = {
    LIKE: "👍",
    LOVE: "❤️",
    HAHA: "😆",
    WOW: "😮",
    SAD: "😥",
    ANGRY: "😡",
    CARE: "🥰",
};

/**
 * Convert the reactions counts to the sorted emojis version.
 * E.G.
 * input: {"LIKE": 9, "CARE": 11, "LOVE": 1}
 * output: [['🥰', 11, like], ['👍', 9, care], ['❤️', 1, love]]
 */
export function formatFacebookReactions(reactions, limit) {
    let sorted = Object.entries(reactions || {})
        .filter(([_reactionName, reactionCount]) => reactionCount !== 0)
        .sort(
            ([_reactionName1, reactionCount1], [_reactionName2, reactionCount2]) =>
                reactionCount2 - reactionCount1
        );

    if (limit) {
        sorted = sorted.slice(0, limit);
    }

    return sorted.map(([reactionName, reactionCount]) => [
        _FACEBOOK_REACTIONS[reactionName],
        reactionCount,
        reactionName.toLowerCase(),
    ]);
}
