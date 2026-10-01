import { AbstractFigureClipboardHandler, registries } from "@odoo/o-spreadsheet";
const { clipboardHandlersRegistries } = registries;

class OdooLinkClipboardHandler extends AbstractFigureClipboardHandler {
    copy(data) {
        const sheetId = this.getters.getActiveSheetId();
        const chartOdooLink = {};
        for (const figureId of data.figureIds) {
            const figure = this.getters.getFigure(sheetId, figureId);
            if (!figure) {
                throw new Error(`No figure for the given id: ${figureId}`);
            }

            if (figure.tag === "chart") {
                const chartId = this.getters.getChartIdFromFigureId(figureId);
                const odooLink = this.getters.getChartOdooLink(chartId);
                chartOdooLink[figureId] = [odooLink];
            } else if (figure.tag === "carousel") {
                const carousel = this.getters.getCarousel(figureId);
                chartOdooLink[figureId] = [];
                for (const item of carousel.items) {
                    if (item.type === "chart") {
                        const odooLink = this.getters.getChartOdooLink(item.chartId);
                        chartOdooLink[figureId].push(odooLink);
                    }
                }
            }
        }

        return { chartOdooLink };
    }
    paste(target, clippedContent, options) {
        if (!target.figureIds) {
            return;
        }
        for (const oldFigureId in target.figureIds) {
            const chartOdooLink = clippedContent.chartOdooLink[oldFigureId];
            if (!chartOdooLink) {
                continue;
            }
            const figureId = target.figureIds[oldFigureId];
            const figure = this.getters.getFigure(target.sheetId, figureId);

            const chartIds = [];
            if (figure.tag === "chart") {
                chartIds.push(this.getters.getChartIdFromFigureId(figureId));
            } else if (figure.tag === "carousel") {
                const carousel = this.getters.getCarousel(figureId);
                for (const item of carousel.items) {
                    if (item.type === "chart") {
                        chartIds.push(item.chartId);
                    }
                }
            }

            for (let i = 0; i < chartIds.length; i++) {
                const chartId = chartIds[i];
                const odooLink = chartOdooLink[i];
                if (odooLink) {
                    this.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
                        chartId,
                        odooLink,
                    });
                }
            }
        }
    }
}

clipboardHandlersRegistries.figureHandlers.add("odoo_datasource", OdooLinkClipboardHandler);
