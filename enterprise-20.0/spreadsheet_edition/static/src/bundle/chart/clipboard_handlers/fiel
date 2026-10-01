import { AbstractFigureClipboardHandler, registries } from "@odoo/o-spreadsheet";
import { globalFieldMatchingRegistry } from "@spreadsheet/global_filters/helpers";
import { deepEqual } from "@web/core/utils/objects";

const { clipboardHandlersRegistries } = registries;

class OdooChartFieldMatchingClipboardHandler extends AbstractFigureClipboardHandler {
    copy({ figureIds }) {
        const sheetId = this.getters.getActiveSheetId();
        const copiedFieldMatchings = {};
        for (const figureId of figureIds) {
            const figure = this.getters.getFigure(sheetId, figureId);
            if (!figure) {
                throw new Error(`No figure for the given id: ${figureId}`);
            }

            if (figure.tag === "chart") {
                const chartId = this.getters.getChartIdFromFigureId(figureId);
                const chart = this.getters.getChart(chartId);
                const fieldMatching =
                    chart.dataSource?.type === "odoo"
                        ? this.getters.getChartFieldMatch(chartId)
                        : undefined;
                copiedFieldMatchings[figureId] = [{ oldChartId: chartId, fieldMatching }];
            } else if (figure.tag === "carousel") {
                const carousel = this.getters.getCarousel(figureId);
                copiedFieldMatchings[figureId] = [];
                for (const item of carousel.items) {
                    if (item.type === "chart") {
                        const chart = this.getters.getChart(item.chartId);
                        const fieldMatching =
                            chart.dataSource?.type === "odoo"
                                ? this.getters.getChartFieldMatch(item.chartId)
                                : undefined;
                        copiedFieldMatchings[figureId].push({
                            oldChartId: item.chartId,
                            fieldMatching,
                        });
                    }
                }
            }
        }

        return { copiedFieldMatchings };
    }

    paste(target, clippedContent, options) {
        if (!target.figureIds) {
            return;
        }
        for (const figureId in target.figureIds) {
            const newFigureId = target.figureIds[figureId];
            const copiedFieldMatchings = clippedContent.copiedFieldMatchings[figureId];
            if (!copiedFieldMatchings) {
                continue;
            }
            const figure = this.getters.getFigure(target.sheetId, newFigureId);
            if (!figure) {
                throw new Error(`No figure for the given id: ${newFigureId}`);
            }

            const chartIds = [];
            if (figure.tag === "chart") {
                chartIds.push(this.getters.getChartIdFromFigureId(newFigureId));
            } else if (figure.tag === "carousel") {
                const carousel = this.getters.getCarousel(newFigureId);
                for (const item of carousel.items) {
                    if (item.type === "chart") {
                        chartIds.push(item.chartId);
                    }
                }
            }

            const filterIds = new Set(
                copiedFieldMatchings.map((fm) => Object.keys(fm.fieldMatching || {})).flat()
            );

            const odooChartIds = globalFieldMatchingRegistry.get("chart").getIds(this.getters);
            for (const filterId of filterIds) {
                const filter = this.getters.getGlobalFilter(filterId);
                const currentChartMatchings = {};
                // copy existing matching of other chars for this filter
                for (const chartId of odooChartIds) {
                    currentChartMatchings[chartId] = this.getters.getOdooChartFieldMatching(
                        chartId,
                        filterId
                    );
                }
                const newChartMatchings = { ...currentChartMatchings };

                for (let i = 0; i < chartIds.length; i++) {
                    const chartId = chartIds[i];

                    const { oldChartId, fieldMatching } = copiedFieldMatchings[i];

                    const copiedFieldMatching = fieldMatching[filterId];
                    if (options?.isCutOperation) {
                        delete newChartMatchings[oldChartId];
                    }
                    newChartMatchings[chartId] = copiedFieldMatching;
                }
                if (deepEqual(newChartMatchings, currentChartMatchings)) {
                    // avoid dispatching a command if the automatic field matching already set
                    // the same matching
                    continue;
                }
                this.dispatch("EDIT_GLOBAL_FILTER", {
                    filter,
                    chart: newChartMatchings,
                });
            }
        }
    }
}

clipboardHandlersRegistries.figureHandlers.add(
    "odoo_chart_field_matching",
    OdooChartFieldMatchingClipboardHandler
);
