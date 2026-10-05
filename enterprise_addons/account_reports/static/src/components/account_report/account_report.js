import { registry } from "@web/core/registry";
import { useVirtualGrid } from "@web/core/virtual_grid_hook";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { useSetupAction } from "@web/search/action_hook";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { UIPlugin } from "@web/core/ui/ui_plugin";

import { Component, onWillDestroy, computed, providePlugins, signal, t, usePlugin, useProps, useScope } from "@odoo/owl";

import { AccountReportButtonsBar } from "@account_reports/components/account_report/buttons_bar/buttons_bar";
import { AccountReportChatter } from "@account_reports/components/mail/chatter";
import { AccountReportCogMenu } from "@account_reports/components/account_report/cog_menu/cog_menu";
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportSearchBar } from "@account_reports/components/account_report/search_bar/search_bar";


class AccountReportPadding extends Component {
    static template = "account_reports.AccountReportPadding";
    props = useProps({ height: t.signal(t.number()) });
}

export class AccountReport extends Component {
    static template = "account_reports.AccountReport";
    static components = {
        ControlPanel,
        AccountReportButtonsBar,
        AccountReportChatter,
        AccountReportCogMenu,
        AccountReportPadding,
        AccountReportSearchBar,
    };
    props = useProps(standardActionServiceProps);

    rootRef = signal.ref();
    virtualScrollableRef = signal.ref();

    ui = usePlugin(UIPlugin);
    scope = useScope();

    setup() {
        useSetupAction({
            rootRef: this.rootRef,
            getLocalState: () => ({ keep_journal_groups_options: true }),  // used when using the breadcrumb
        });
        if (this.props?.state?.keep_journal_groups_options !== undefined) {
            this.props.action.keep_journal_groups_options = true;
        }

        // The scrollable element is different if we are on a small device or not due to the flex-direction used on the o_content.
        const scrollableRef = computed(() => this.ui.isSmall() ? this.rootRef() : this.virtualScrollableRef());
        function createVirtualGrids() {
            return {
                left: useVirtualGrid({
                    scrollableRef,
                    /** Lines are very expensive to render since they contain a lot of logic and sub components.
                     * Since this buffer is for the top **AND** bottom, it will add 2 lines for every line added in a direction
                     * making it quickly more expensive. Another reason to keep this low is to not overload the DOM with too many
                     * elements, which can drastically reduce the performance.
                     */
                    bufferCoef: 0.5,
                }),
                right: useVirtualGrid({  // Right table for horizontal split, if enabled
                    scrollableRef,
                    bufferCoef: 0.5,
                }),
            };
        }
        const virtualGrids = computed(() => {
            this.controller?._invalidateVisibleLines.set(true);
            return this.scope.run(() => createVirtualGrids());
        });

        providePlugins([AccountReportController], {
            action: this.props.action,
            scrollableRef,
            virtualGrids,
        });
        this.controller = usePlugin(AccountReportController);
        this.initialQuery = this.props.action.context.default_filter_accounts || '';

        onWillDestroy(() => {
            // Since the controller is preloading the sections using a setTimeout, it's never stopped unless we explicitly tell it.
            this.controller.destroyed = true;
        });

        this.cssCustomClass = computed(() => this.controller.options().custom_display_config.css_custom_class || "");
        this.tableClasses = computed(() => this.getTableClasses());
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Table
    // -----------------------------------------------------------------------------------------------------------------
    getTableClasses() {
        let classes = "";

        if (this.controller.options().columns.length > 1)
            classes += " striped";

        if (this.controller.options().horizontal_split)
            classes += " w-50 mx-2";

        return classes;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Chatter
    // -----------------------------------------------------------------------------------------------------------------
    /**
     * @param {KeyboardEvent} ev
     */
    onKeydown(ev) {
        if (ev.key === "Escape") {
            this.controller.closeChatter();
        }
    }

    /**
     * @param {MouseEvent} ev 
     */
    onClick(ev) {
        if (this.ui.isSmall() && this.controller.chatterState.id() && !ev.target.closest(".o_account_report_mobile_chatter")) {
            this.controller.closeChatter();
        }
    }
}

registry.category("actions").add("account_report", AccountReport);
