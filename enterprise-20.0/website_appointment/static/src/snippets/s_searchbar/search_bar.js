import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@website/snippets/s_searchbar/search_bar";

patch(SearchBar.prototype, {
    /**
     * Allows to keep the invite token and the filters in the URL
     * parameters after clicking on the search bar suggestions.
     *
     * @override
     */
    render(res) {
        if (res && this.searchType === 'appointments' && res.parts.website_url) {
            const parser = new DOMParser();
            const doc = parser.parseFromString(res.results, "text/html");
            const search = location.search;

            doc.querySelectorAll("a.o_search_result_link").forEach((a) => {
                const href = a.getAttribute("href");
                if (!href) {
                    return;
                }
                const newUrl = href.includes("?")
                    ? `${href}&${search.slice(1)}`
                    : `${href}${search}`;
                a.setAttribute("href", newUrl);
            });

            res.results = doc.body.innerHTML;
        }
        super.render(...arguments);
    },
});
