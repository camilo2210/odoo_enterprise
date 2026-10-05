export function searchInPopup(query) {
    return {
        content: `Type "${query}" in the resource search field`,
        trigger: `.modal-header .search-input input`,
        run: `edit ${query}`,
    };
}

export function clickResourceInPopup(resourceName) {
    return {
        content: `Select resource "${resourceName}" from the popup`,
        trigger: `.modal-body tr.slot-line td b:contains("${resourceName}")`,
        run: "click",
    };
}
