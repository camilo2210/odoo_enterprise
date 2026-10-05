import { Component, t, useProps } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";

/**
 * Message displayed in a softphone tab when there are no search results.
 */
export class NoSearchResults extends Component {
    static template = "voip.NoSearchResults";

    props = useProps({
        actionCallback: t.function(),
        actionMessage: t.string(),
        icon: t.string(),
        noResultsMessage: t.string(),
    });

    setup() {
        this.action = useService("action");
    }
}
