import { browser } from "@web/core/browser/browser";
import { makeContext } from "@web/core/context";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Restores the user preferred documents view mode ("kanban" or "list").
 * Not applied in mobile environments (uses the "mobile_view_mode"
 * action field which defaults on "kanban").
 */
async function documentActionPreference(env, actionDescr, options) {
    const action = useService("action");

    const viewType = browser.localStorage.getItem("documentsDefaultViewType");
    const nextAction = await action.loadAction("documents.document_action");

    return action.doAction(
        {
            ...nextAction,
            context: makeContext([actionDescr.context, { skip_res_field_check: true }]),
            domain: actionDescr.domain,
        },
        { ...options, viewType }
    );
}

registry.category("actions").add("document_action_preference", documentActionPreference);
