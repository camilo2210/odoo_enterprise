import { render } from "@web/owl2/utils";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { Mutex } from "@web/core/utils/concurrency";
import { useBus, useService } from "@web/core/utils/hooks";
import { computeAppsAndMenuItems, reorderApps } from "@web/webclient/menus/menu_helpers";
import {
    ControllerNotFoundError,
    standardActionServiceProps,
} from "@web/webclient/actions/action_plugin";
import { HomeMenu } from "./home_menu";

import { Component, onMounted, onWillUnmount, proxy, useProps, xml } from "@odoo/owl";

export const homeMenuService = {
    dependencies: ["action"],
    start(env, { action }) {
        const state = proxy({
            hasHomeMenu: false, // true iff the HomeMenu is currently displayed
            hasBackgroundAction: false, // true iff there is an action behind the HomeMenu
            toggle,
        });
        const mutex = new Mutex(); // used to protect against concurrent toggling requests
        class HomeMenuAction extends Component {
            static components = { HomeMenu };
            static target = "current";
            static template = xml`<HomeMenu t-props="this.homeMenuProps"/>`;
            static displayName = _t("Home");

            props = useProps(standardActionServiceProps);

            setup() {
                this.menus = useService("menu");
                onMounted(() => this.onMounted());
                onWillUnmount(this.onWillUnmount);
                useBus(this.env.bus, "MENUS:APP-CHANGED", () => render(this));
            }
            get homeMenuProps() {
                const homemenuConfig = JSON.parse(user.settings?.homemenu_config || "null");
                const apps = computeAppsAndMenuItems(this.menus.getMenuAsTree("root")).apps;
                if (homemenuConfig) {
                    reorderApps(apps, homemenuConfig);
                }
                const reactiveApps = proxy(apps);
                return {
                    apps: reactiveApps,
                    reorderApps: (order) => reorderApps(reactiveApps, order),
                };
            }
            async onMounted() {
                const { breadcrumbs } = this.env.config;
                state.hasHomeMenu = true;
                state.hasBackgroundAction = breadcrumbs.length > 0;
                this.env.bus.trigger("HOME-MENU:TOGGLED");
            }
            onWillUnmount() {
                state.hasHomeMenu = false;
                state.hasBackgroundAction = false;
                this.env.bus.trigger("HOME-MENU:TOGGLED");
            }
        }

        registry.category("actions").add("menu", HomeMenuAction);

        env.bus.addEventListener("HOME-MENU:TOGGLED", () => {
            document.body.classList.toggle("o_home_menu_background", state.hasHomeMenu);
        });

        async function toggle(show) {
            return mutex.exec(async () => {
                show = show === undefined ? !state.hasHomeMenu : Boolean(show);
                if (show !== state.hasHomeMenu) {
                    if (show) {
                        await action.doAction("menu");
                    } else {
                        try {
                            await action.restore();
                        } catch (err) {
                            if (!(err instanceof ControllerNotFoundError)) {
                                throw err;
                            }
                        }
                    }
                }
                // hack: wait for a tick to ensure that the url has been updated before
                // switching again
                return new Promise((r) => setTimeout(r));
            });
        }

        return state;
    },
};

registry.category("services").add("home_menu", homeMenuService);
