import { aiClientToolsRegistry } from "@ai/discuss/core/common/ai_client_tool_registry";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

aiClientToolsRegistry.add("reload", async (thread, params) => {
    await thread.store.env.services.action.doAction({
        type: "ir.actions.client",
        tag: "soft_reload",
    });
});

aiClientToolsRegistry.add("do_action", async (thread, params) => {
    await thread.store.env.services.action.doAction(params.action);
});

aiClientToolsRegistry.add("show_view", async (thread, params) => {
    const { services } = thread.store.env;
    const { action, options = {}, menuId = null } = params;
    if (menuId) {
        options.clearBreadcrumbs = true;
        options.onActionReady = () => services.menu.setCurrentMenu(menuId);
    }
    await services.action.doAction(action, options);
});

aiClientToolsRegistry.add("adjust_view", async (thread, params) => {
    const { env } = thread.store;
    const switchViewType = params.switchViewType;
    if (switchViewType) {
        try {
            await env.services.action.switchView(switchViewType);
        } catch {
            env.services.dialog.add(AlertDialog, {
                body: _t(
                    "Tried to switch to %s but the app is no longer in an action window.",
                    switchViewType,
                ),
                title: _t("Unable to switch view"),
                confirm: () => {},
                confirmLabel: _t("Close"),
            });
            return;
        }
    }
    env.bus.trigger("APPLY_AI_ADJUST_SEARCH", params);
});
