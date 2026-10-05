import { NavBar } from "@web/webclient/navbar/navbar";
import { useService, useBus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onPatched, signal } from "@odoo/owl";

export class EnterpriseNavBar extends NavBar {
    static template = "web_enterprise.EnterpriseNavBar";
    navRef = signal.ref();
    appIconRef = signal.ref();
    setup() {
        super.setup();
        this.hm = useService("home_menu");
        this.pwa = useService("pwa");
        this._busToggledCallback = () => this._updateMenuAppsIcon();
        useBus(this.env.bus, "HOME-MENU:TOGGLED", this._busToggledCallback.bind(this));
        onMounted(() => this._updateMenuAppsIcon());
        onPatched(() => this._updateMenuAppsIcon());
    }
    get hasBackgroundAction() {
        return this.hm.hasBackgroundAction;
    }
    get isInApp() {
        return !this.hm.hasHomeMenu;
    }

    _openAppMenuSidebar() {
        if (this.hm.hasHomeMenu) {
            this.hm.toggle(false);
        } else {
            this.state.isAppMenuSidebarOpened = true;
        }
    }
    _updateMenuAppsIcon() {
        const menuAppsEl = this.menuApps();
        menuAppsEl.classList.toggle("o_hidden", !this.isInApp && !this.hasBackgroundAction);
        menuAppsEl.classList.toggle(
            "o_menu_toggle_back",
            !this.isInApp && this.hasBackgroundAction
        );
        if (!this.isScopedApp) {
            const title =
                !this.isInApp && this.hasBackgroundAction ? _t("Previous view") : _t("Home menu");
            menuAppsEl.title = title;
            menuAppsEl.ariaLabel = title;
        }

        const menuBrand = this.navRef().querySelector(".o_menu_brand");
        if (menuBrand) {
            menuBrand.classList.toggle("o_hidden", !this.isInApp);
        }

        const menuBrandIcon = this.navRef().querySelector(".o_menu_brand_icon");
        if (menuBrandIcon) {
            menuBrandIcon.classList.toggle("o_hidden", !this.isInApp);
        }

        const appSubMenus = this.appSubMenus();
        if (appSubMenus) {
            appSubMenus.classList.toggle("o_hidden", !this.isInApp);
        }

        const breadcrumb = this.navRef().querySelector(".o_breadcrumb");
        if (breadcrumb) {
            breadcrumb.classList.toggle("o_hidden", !this.isInApp);
        }
    }

    /**
     * @override
     */
    onAllAppsBtnClick() {
        super.onAllAppsBtnClick();
        this.hm.toggle(true);
        this._closeAppMenuSidebar();
    }
}
