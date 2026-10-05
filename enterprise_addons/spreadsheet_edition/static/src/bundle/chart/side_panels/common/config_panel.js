import { Domain } from "@web/core/domain";
import { DomainSelector } from "@web/core/domain_selector/domain_selector";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { components, constants } from "@odoo/o-spreadsheet";

import { asyncComputed, Component, onWillStart, t, usePlugin, useProps } from "@odoo/owl";
import { RelatedFiltersSection } from "../../../global_filters/components/related_filters_section/related_filters_section";
import { OdooLinkSelector } from "../../link_datasource/odoo_link_selector";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

const { Checkbox, Section, ValidationMessages } = components;
const { ChartTerms } = constants;

export class OdooChartDataSourceConfigPanel extends Component {
    static template = "spreadsheet_edition.OdooChartDataSourceConfigPanel";
    static components = {
        Checkbox,
        DomainSelector,
        RelatedFiltersSection,
        Section,
        ValidationMessages,
        OdooLinkSelector,
    };

    props = useProps({
        chartId: t.string(),
        definition: t.object(),
        updateChart: t.function(),
        canUpdateChart: t.function(),
        getLabelRangeOptions: t.function().optional(),
        figureId: t.any().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);

    chartTerms = ChartTerms;

    chartData = asyncComputed(async () => {
        const dataSource = this.env.model.getters.getChartDataSource(this.props.chartId);
        await dataSource.load();
        const isModelValid = dataSource.isModelValid();
        const isDataLoaded = dataSource.isReady();
        const modelDisplayName = isModelValid ? await dataSource.getModelLabel() : undefined;

        return {
            isModelValid,
            isDataLoaded,
            modelDisplayName,
        };
    });

    setup() {
        this.dialog = useService("dialog");
        onWillStart(() => this.chartData.currentPromise());
    }

    get invalidChartModel() {
        const model = this.env.model.getters.getChartDefinition(this.props.chartId).dataSource
            .metaData.resModel;
        return _t(
            "The model (%(model)s) of this chart is not valid (it may have been renamed/deleted). Please re-insert a new chart.",
            {
                model,
            }
        );
    }

    get model() {
        const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
        return definition.dataSource.metaData.resModel;
    }

    get domain() {
        const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
        return new Domain(definition.dataSource.searchParams.domain).toString();
    }

    getLabelRangeOptions() {
        if (this.props.getLabelRangeOptions) {
            // aggregated doesn't make sense for odoo datasource,
            // it's always aggregated server-side
            return this.props
                .getLabelRangeOptions()
                .filter((option) => option.name !== "aggregated");
        }
        return [];
    }

    onNameChanged(title) {
        const definition = {
            ...this.env.model.getters.getChartDefinition(this.props.chartId),
            title,
        };
        const figureId = this.env.model.getters.getFigureIdFromChartId(this.props.chartId);
        this.env.model.dispatch("UPDATE_CHART", {
            chartId: this.props.chartId,
            figureId,
            sheetId: this.env.model.getters.getFigureSheetId(figureId),
            definition,
        });
    }

    /**
     * Get the last update date, formatted
     *
     * @returns {string} date formatted
     */
    getLastUpdate() {
        const dataSource = this.env.model.getters.getChartDataSource(this.props.chartId);
        const lastUpdate = dataSource.lastUpdate;
        if (lastUpdate) {
            return new Date(lastUpdate).toLocaleTimeString();
        }
        return _t("never");
    }

    openDomainEdition() {
        this.dialog.add(DomainSelectorDialog, {
            resModel: this.model,
            domain: new Domain(this.domain).toString(),
            isDebugMode: this.debugMode.isActive(),
            onConfirm: (domain) => {
                const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
                const updatedDefinition = {
                    ...definition,
                    dataSource: {
                        ...definition.dataSource,
                        searchParams: {
                            ...definition.dataSource.searchParams,
                            domain: new Domain(domain).toJson(),
                        },
                    },
                };
                const figureId = this.env.model.getters.getFigureIdFromChartId(this.props.chartId);
                this.env.model.dispatch("UPDATE_CHART", {
                    chartId: this.props.chartId,
                    figureId,
                    sheetId: this.env.model.getters.getFigureSheetId(figureId),
                    definition: updatedDefinition,
                });
            },
        });
    }

    delete() {
        this.env.model.dispatch("DELETE_FIGURE", { figureId: this.props.figureId });
    }
}
