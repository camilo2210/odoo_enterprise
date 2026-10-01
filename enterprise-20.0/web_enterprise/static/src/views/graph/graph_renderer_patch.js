import { patch } from "@web/core/utils/patch";
import { GraphRenderer } from "@web/views/graph/graph_renderer";
import {
    darkenColor,
    getCustomColor,
    lightenColor,
} from "@web/core/colors/colors";
import { cookie } from "@web/core/browser/cookie";
import { sortBy } from "@web/core/utils/arrays";

const colorScheme = cookie.get("color_scheme");

const BAR_BORDER_RADIUS = 4;
const AREA_FADE_LIGHT = "#FFFFFF";
const AREA_FADE_DARK = "rgb(38, 42, 54)";

/**
 * Builds a linear gradient over an arbitrary rect (in canvas coordinates),
 * emulating a CSS `linear-gradient(angleDeg, ...)`. The gradient line is
 * sized and centered on the rect itself (not the whole chart area), so e.g.
 * a bar's own natural color shows at its own edge, not at the chart's edge.
 * @param {CanvasRenderingContext2D} ctx
 * @param {{x: number, y: number, width: number, height: number}} rect canvas coordinates
 * @param {number} angleDeg CSS gradient angle (0 = to top, clockwise)
 * @param {[number, string][]} colorStops
 * @returns {CanvasGradient}
 */
function getAngledGradient(ctx, rect, angleDeg, colorStops) {
    const { x, y, width, height } = rect;
    const angle = ((angleDeg % 360) + 360) % 360;
    const rad = (angle * Math.PI) / 180;
    // Length/orientation of the gradient line, per the CSS spec formula for
    // an angled gradient over a box of a given size.
    const length = Math.abs(width * Math.sin(rad)) + Math.abs(height * Math.cos(rad));
    const halfX = (Math.sin(rad) * length) / 2;
    const halfY = (Math.cos(rad) * length) / 2;
    const cx = x + width / 2;
    const cy = y + height / 2;
    const gradient = ctx.createLinearGradient(cx - halfX, cy + halfY, cx + halfX, cy - halfY);
    for (const [offset, color] of colorStops) {
        gradient.addColorStop(offset, color);
    }
    return gradient;
}

/**
 * Mixes a color towards the theme's "white" (light mode) or "black" (dark
 * mode), i.e. `mix(color, white, 80%)` in bright mode and its dark
 * counterpart in dark mode.
 * @param {string} color
 * @param {number} [factor=0.5]
 * @returns {string}
 */
function getLightVariant(color, factor = 0.5) {
    return getCustomColor(colorScheme, lightenColor(color, factor), darkenColor(color, factor));
}

/**
 * Chart.js elements can exist as objects before their geometry has actually
 * been computed (e.g. the very first paint tick, before any animation has
 * run): their x/y/width/... fields are then `undefined`, which silently
 * turns into `NaN` through arithmetic and makes `createLinearGradient`/
 * `createRadialGradient` throw ("Argument is not a finite floating-point
 * value"). Every gradient built below must check this first.
 * @param {number[]} values
 * @returns {boolean}
 */
function allFinite(values) {
    return values.every(Number.isFinite);
}

patch(GraphRenderer.prototype, {
    /**
     * Bars have no border. No gradient fill here (unlike line/pie): Chart.js
     * resolves scriptable dataset options like `backgroundColor` once,
     * before the "grow from baseline" entry animation reaches its final
     * geometry, so a gradient sized to each bar's own rect gets built from a
     * near-zero-height rect and stays wrong until something else (hover,
     * resize) forces an unrelated redraw. Forcing that redraw ourselves via
     * `chart.update()` from `animation.onComplete` recurses into Chart.js'
     * own render call stack, since `onComplete` fires from inside it - not
     * worth chasing further for a fill this subtle, so bars stay flat.
     * @override
     */
    getElementOptions() {
        const elementOptions = super.getElementOptions();
        if (this.model.metaData.mode === "bar") {
            elementOptions.bar = { ...elementOptions.bar, borderWidth: 0};
        }
        return elementOptions;
    },

    /**
     * Area charts: gradient fill from a dimmed variant of the base color to
     * fully transparent.
     * @override
     */
    getLineChartData() {
        const data = super.getLineChartData();
        for (const dataset of data.datasets) {
            const itemColor = dataset.borderColor;
            dataset.backgroundColor = (context) => {
                const chart = context.chart;
                const chartArea = chart?.chartArea;
                if (!chartArea) {
                    return itemColor;
                }
                const rect = {
                    x: chartArea.left,
                    y: chartArea.top,
                    width: chartArea.right - chartArea.left,
                    height: chartArea.bottom - chartArea.top,
                };
                if (!allFinite([rect.x, rect.y, rect.width, rect.height])) {
                    return itemColor;
                }
                return getAngledGradient(chart.ctx, rect, 180, [
                    [0, getLightVariant(itemColor)],
                    [1, getCustomColor(colorScheme, AREA_FADE_LIGHT, AREA_FADE_DARK)],
                ]);
            };
        }
        return data;
    },

    /**
     * Pie: gradient fill from the full base color (center) to a light
     * variant of it (edge), no border.
     * @override
     */
    getPieChartData() {
        const data = super.getPieChartData();
        for (const dataset of data.datasets) {
            const colors = dataset.backgroundColor;
            const backgroundColor = (context) => {
                const color = colors[context.dataIndex];
                const arc = context.element;
                if (!arc || !color) {
                    // No element to compute a radial gradient on yet
                    return color;
                }
                const { x, y, outerRadius, innerRadius } = arc.getProps(
                    ["x", "y", "outerRadius", "innerRadius"],
                    true
                );
                if (!allFinite([x, y, outerRadius, innerRadius]) || outerRadius <= 0) {
                    return color;
                }
                const gradient = context.chart.ctx.createRadialGradient(
                    x,
                    y,
                    innerRadius,
                    x,
                    y,
                    outerRadius
                );
                gradient.addColorStop(0, color);
                gradient.addColorStop(1, getLightVariant(color, 0.1));
                return gradient;
            };
            dataset.backgroundColor = backgroundColor;
            dataset.hoverBackgroundColor = backgroundColor;
            dataset.borderColor = "transparent";
            dataset.borderWidth = 0;
        }
        return data;
    },

    /**
     * @override
     */
    getLegendOptions() {
        const legendOptions = super.getLegendOptions();
        const generateLabels = legendOptions.labels.generateLabels;

        legendOptions.labels = { ...legendOptions.labels, boxWidth: 30 };
        legendOptions.labels.generateLabels = (chart) => {
            const labels = generateLabels(chart);
            for (const label of labels) {
                label.borderRadius = BAR_BORDER_RADIUS;
            }
            return labels;
        };
        return legendOptions;
    },

    /**
     * @override
     */
    getTooltipItems(data, metaData, tooltipModel) {
        const items = super.getTooltipItems(data, metaData, tooltipModel);
        if (metaData.mode === "pie") {
            const sortedDataPoints = sortBy(tooltipModel.dataPoints, "raw", "desc");
            items.forEach((item, i) => {
                const { datasetIndex, dataIndex } = sortedDataPoints[i];
                const backgroundColor = data.datasets[datasetIndex].backgroundColor;
                if (typeof backgroundColor === "function") {
                    item.boxColor = backgroundColor({ dataIndex });
                }
            });
        }
        return items;
    },
});
