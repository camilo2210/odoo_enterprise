import { render } from "@web/owl2/utils";
import { registry } from "@web/core/registry";
import { user as originalUser } from "@web/core/user";
import { useBus, useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { computeAppsAndMenuItems, reorderApps } from "@web/webclient/menus/menu_helpers";

import { AppCreator } from "./app_creator/app_creator";
import { Editor } from "./editor/editor";
import { StudioNavbar } from "./navbar/navbar";
import { StudioHomeMenu } from "./studio_home_menu/studio_home_menu";

import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useProps } from "@odoo/owl";

export class StudioClientAction extends Component {
    static template = "web_studio.StudioClientAction";
    static target = "fullscreen";
    static components = {
        StudioNavbar,
        StudioHomeMenu,
        Editor,
        AppCreator,
    };

    props = useProps(standardActionServiceProps);

    setup() {
        const homemenuConfig = JSON.parse(originalUser.settings?.homemenu_config || "null");
        this.studio = useService("studio");
        useBus(this.studio.bus, "UPDATE", () => {
            render(this);
        });

        this.menus = useService("menu");
        this.actionService = useService("action");
        let apps = computeAppsAndMenuItems(this.menus.getMenuAsTree("root")).apps;
        if (homemenuConfig) {
            reorderApps(apps, homemenuConfig);
        }
        this.homeMenuProps = {
            apps: apps,
        };
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            apps = computeAppsAndMenuItems(this.menus.getMenuAsTree("root")).apps;
            if (homemenuConfig) {
                reorderApps(apps, homemenuConfig);
            }
            this.homeMenuProps = {
                apps: apps,
            };
            render(this);
        });

        onWillStart(() => this.studio.ready);
        onMounted(() => {
            document.body.classList.add("o_in_studio");
            this.studio.pushState();
        });
        onPatched(() => this.studio.pushState());
        onWillUnmount(() => document.body.classList.remove("o_in_studio"));
    }

    async onNewAppCreated({ action_id, menu_id }) {
        await this.menus.reload();
        this.menus.setCurrentMenu(menu_id);
        const action = await this.actionService.loadAction(action_id);

        let initViewType = "form";
        if (!action.views.some((vTuple) => vTuple[1] === initViewType)) {
            initViewType = action.views[0][1];
        }
        this.studio.setParams({
            mode: this.studio.MODES.EDITOR,
            editorTab: "views",
            action,
            viewType: initViewType,
        });
    }
}

registry.category("lazy_components").add("StudioClientAction", StudioClientAction);
// force: true to bypass the studio lazy loading action next time and just use this one directly
registry.category("actions").add("studio", StudioClientAction, { force: true });
