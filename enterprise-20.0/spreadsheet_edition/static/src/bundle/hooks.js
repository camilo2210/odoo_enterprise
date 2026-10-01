import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { SPREADSHEET_DIMENSIONS } from "@odoo/o-spreadsheet";

/**
 * @returns {Promise<Array>}
 */
export function useSpreadsheetLocales() {
    const orm = useService("orm");
    async function loadLocales() {
        return orm.call("res.lang", "get_locales_for_spreadsheet", []);
    }
    return loadLocales;
}

/**
 * @returns {Promise<Array>}
 */
export function useSpreadsheetCurrencies() {
    const orm = useService("orm");
    async function loadCurrencies() {
        const odooCurrencies = await orm.searchRead(
            "res.currency", // model
            [], // domain
            ["symbol", "full_name", "position", "name", "decimal_places"], // fields
            {
                // opts
                order: "active DESC, full_name ASC",
                context: { active_test: false },
            }
        );
        return odooCurrencies.map((currency) => ({
            code: currency.name,
            symbol: currency.symbol,
            position: currency.position || "after",
            name: currency.full_name || _t("Currency"),
            decimalPlaces: currency.decimal_places || 2,
        }));
    }
    return loadCurrencies;
}

/**
 * @returns {() => (string | undefined)}
 */
export function useSpreadsheetThumbnail() {
    return () => {
        const dimensions = SPREADSHEET_DIMENSIONS;
        const dpr = window.devicePixelRatio || 1;
        const canvas = document.querySelector(".o-grid canvas:not(.o-figure-canvas)");
        if (!canvas) {
            return undefined;
        }
        const canvasResizer = document.createElement("canvas");
        const height = 500;
        const aspectRatio = 200 / 140;
        const width = height * aspectRatio;
        canvasResizer.width = width;
        canvasResizer.height = height;
        const canvasCtx = canvasResizer.getContext("2d");
        // use only 25 first rows in thumbnail
        const sourceHeight = Math.min(
            25 * dimensions.DEFAULT_CELL_HEIGHT,
            canvas.width / aspectRatio,
            canvas.height
        );
        const sourceWidth = sourceHeight * aspectRatio;
        const sizeRatio = (height / sourceHeight) * dpr;
        if (canvas.width !== 0 && canvas.height !== 0) {
            canvasCtx.drawImage(
                canvas,
                dimensions.HEADER_WIDTH * dpr - 1,
                dimensions.HEADER_HEIGHT * dpr - 1,
                sourceWidth,
                sourceHeight,
                0,
                0,
                width,
                height
            );
            let { top: canvasTop, left: canvasLeft } = canvas.getBoundingClientRect();
            canvasLeft += dimensions.HEADER_WIDTH - 1;
            canvasTop += dimensions.HEADER_HEIGHT - 1;
            for (const chart of document.querySelectorAll(".o-figure .o-chart-container")) {
                const figureCanvas = chart.querySelector(".o-figure-canvas");
                if (!figureCanvas) {
                    continue;
                }
                const {
                    top: figureTop,
                    left: figureLeft,
                    width: figureWidth,
                    height: figureHeight,
                } = figureCanvas.getBoundingClientRect();
                const divBGColor = chart.children[0].style.backgroundColor;
                if (divBGColor) {
                    canvasCtx.save();
                    canvasCtx.fillStyle = divBGColor;
                    canvasCtx.fillRect(
                        (figureLeft - canvasLeft) * sizeRatio,
                        (figureTop - canvasTop) * sizeRatio,
                        figureWidth * sizeRatio,
                        figureHeight * sizeRatio
                    );
                    canvasCtx.restore();
                }
                canvasCtx.drawImage(
                    figureCanvas,
                    0,
                    0,
                    figureCanvas.width,
                    figureCanvas.height,
                    (figureLeft - canvasLeft) * sizeRatio,
                    (figureTop - canvasTop) * sizeRatio,
                    figureWidth * sizeRatio,
                    figureHeight * sizeRatio
                );
            }
        }
        const type = "image/webp";
        const quality = 0;
        const dataUrl = canvasResizer.toDataURL(type, quality);
        const regexp = new RegExp("^data:image/.*;base64,");
        return dataUrl.replace(regexp, "");
    };
}
