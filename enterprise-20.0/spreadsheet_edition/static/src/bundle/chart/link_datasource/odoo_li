import { _t } from "@web/core/l10n/translation";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { globalFieldMatchingRegistry } from "@spreadsheet/global_filters/helpers";
import { IrMenuSelector } from "@spreadsheet_edition/bundle/ir_menu_selector/ir_menu_selector";

const { ChartRangeDataSourceComponent, ScorecardChartConfigPanel, GaugeChartConfigPanel, Section } =
    spreadsheet.components;

import {
    asyncComputed,
    Component,
    onWillStart,
    onWillUnmount,
    proxy,
    t,
    useEffect,
    useProps,
} from "@odoo/owl";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";

export class OdooLinkSelector extends Component {
    static template = "spreadsheet_edition.OdooLinkSelector";
    static components = {
        Section,
        RadioSelection: spreadsheet.components.RadioSelection,
        IrMenuSelector,
        AutoComplete,
    };

    props = useProps({
        chartId: t.string(),
    });

    /** @type {ReadComputed<Array<{name: string, dataSourceType: string, dataSourceCoreId: string}>>} */
    dataSources = asyncComputed(async () => {
        const dataSources = [];
        for (const dataSourceType of globalFieldMatchingRegistry.getKeys()) {
            const dsFieldMatching = globalFieldMatchingRegistry.get(dataSourceType);

            for (const dataSourceCoreId of dsFieldMatching.getIds(this.env.model.getters)) {
                const tag = dsFieldMatching.getTag(this.env.model.getters, dataSourceCoreId);
                const displayName = dsFieldMatching.getDisplayName(
                    this.env.model.getters,
                    dataSourceCoreId
                );

                dataSources.push({
                    name: `${tag} - ${displayName}`,
                    dataSourceType,
                    dataSourceCoreId,
                });
            }
        }
        return dataSources;
    });

    setup() {
        super.setup();
        this.linkState = proxy({ type: this.odooLink?.type || "odooMenu" });
        useEffect(() => {
            const dataSources = this.dataSources();
            if (dataSources && dataSources.length === 0 && this.linkState.type !== "odooMenu") {
                this.linkState.type = "odooMenu";
            }
        });
        onWillStart(() => this.dataSources.currentPromise());
        this.env.model.on("update", this, () => this.dataSources.refresh());
        onWillUnmount(() => this.env.model.off("update", this));
    }

    /**
     * @returns {Array<{type: "dataSource", dataSourceType: string, dataSourceCoreId: string}> | undefined}
     */
    get odooLink() {
        return this.env.model.getters.getChartOdooLink(this.props.chartId);
    }

    get odooDataSourceName() {
        const odooLink = this.odooLink;
        if (odooLink?.type !== "dataSource") {
            return undefined;
        }
        const dataSource = this.dataSources().find(
            (ds) =>
                ds.dataSourceType === odooLink.dataSourceType &&
                ds.dataSourceCoreId === odooLink.dataSourceCoreId
        );
        return dataSource?.name;
    }

    selectDataSource(dataSourceType, dataSourceCoreId) {
        if (!dataSourceCoreId) {
            this.env.model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
                chartId: this.props.chartId,
                odooLink: undefined,
            });
            return;
        }
        this.env.model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId: this.props.chartId,
            odooLink: { type: "dataSource", dataSourceType, dataSourceCoreId },
        });
    }

    get odooMenuId() {
        const odooLink = this.odooLink;
        if (!odooLink || odooLink.type !== "odooMenu") {
            return undefined;
        }
        return this.env.model.getters.getIrMenu(odooLink.odooMenuId)?.id;
    }

    async updateOdooMenu(odooMenuId) {
        if (!odooMenuId) {
            this.env.model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
                chartId: this.props.chartId,
                odooLink: undefined,
            });
            return;
        }
        const menu = this.env.model.getters.getIrMenu(odooMenuId);
        this.env.model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId: this.props.chartId,
            odooLink: { type: "odooMenu", odooMenuId: menu.xmlid || menu.id },
        });
    }

    get radioOptions() {
        const options = [{ value: "odooMenu", label: _t("Default menu") }];
        if (this.dataSources().length) {
            options.push({ value: "dataSource", label: _t("Data source") });
        }
        return options;
    }

    get sources() {
        return [
            {
                options: this.dataSources().map((ds) => ({
                    label: ds.name,
                    onSelect: () => this.selectDataSource(ds.dataSourceType, ds.dataSourceCoreId),
                })),
            },
        ];
    }

    openDataSourceSidePanel() {
        const odooLink = this.odooLink;
        if (odooLink?.type !== "dataSource") {
            return undefined;
        }
        const { dataSourceType, dataSourceCoreId } = odooLink;
        globalFieldMatchingRegistry.get(dataSourceType)?.openSidePanel(this.env, dataSourceCoreId);
    }
}

/**
 * Patch the chart configuration panel to add an input to
 * link the chart to an Odoo menu.
 */
function patchChartPanelWithMenu(PanelComponent) {
    PanelComponent.components = {
        ...PanelComponent.components,
        OdooLinkSelector,
    };
}
patchChartPanelWithMenu(GaugeChartConfigPanel);
patchChartPanelWithMenu(ChartRangeDataSourceComponent);
patchChartPanelWithMenu(ScorecardChartConfigPanel);
