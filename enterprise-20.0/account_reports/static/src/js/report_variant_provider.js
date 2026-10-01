import { usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { fuzzyLookup } from "@web/core/utils/search";
import { ORM } from "@web/core/orm_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

const commandProviderRegistry = registry.category("command_provider");

commandProviderRegistry.add("account_report_variants", {
    namespace: "/",
    async provide(options) {
        if (!options.searchValue || options.searchValue.length < 2) {
            return [];
        }

        const action = usePlugin(ActionPlugin);
        const orm = usePlugin(ORM);
        const menuService = useService("menu");
        const apps = menuService.getApps();

        const accountingApp = apps.find((app) =>
            ["accountant.menu_accounting", "account.menu_finance"].includes(app.xmlid)
        );

        if (!accountingApp) {
            return [];
        }

        const variants = await orm.cache({
            type: "disk",
            update: "once",
        }).call("account.report", "get_available_variants", []);

        const matched = fuzzyLookup(options.searchValue, variants, (v) => v.display_name);
        if (!matched.length) return [];

        return matched.slice(0, 5).map((variant) => ({
            name: `${variant.root_report_path_name} / ${variant.display_name}`,
            category: "menu_items",
            action() {
                menuService.setCurrentMenu(accountingApp);

                const reportMenu = menuService.getAll().find((m) => m.actionID && m.actionID == variant.root_action_id);

                action.doAction({
                    type: "ir.actions.client",
                    tag: "account_report",
                    name: variant.display_name,
                    context: { report_id: variant.root_report_id },
                    params: {
                        options: { selected_variant_id: variant.id },
                        ignore_session: true,
                    },
                    path: reportMenu?.actionPath,
                }, { clearBreadcrumbs: true });
            },
        }));
    },
});
