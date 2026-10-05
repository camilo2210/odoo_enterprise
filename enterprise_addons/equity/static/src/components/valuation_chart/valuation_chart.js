/** @odoo-module **/
import {
    Component,
    onWillUnmount,
    onMounted,
    onWillStart,
    onPatched,
    signal,
    t,
    useProps,
} from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { formatPercentage, formatMonetary } from "@web/views/fields/formatters";

export class ValuationChart extends Component {
    static template = "equity.ValuationChart";

    props = useProps({
        labels: t.array(),
        data: t.object(),
        stats: t.object().optional(),
    });

    canvasRef = signal.ref();

    setup() {
        super.setup();
        onWillStart(() => loadJS("/web/static/lib/Chart/Chart.js"));
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
        onWillUnmount(this.destroyChart);
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
        }
    }

    renderChart() {
        this.destroyChart();
        const ctx = this.canvasRef().getContext("2d");
        this.chart = new Chart(ctx, this.getChartConfig());
    }

    getChartConfig() {
        const chartData = this.props.data;

        return {
            type: "line",
            data: {
                labels: Object.keys(chartData),
                datasets: this.props.labels.map((label, index) => {
                    return {
                        label,
                        data: Object.values(chartData).map(tuple => tuple[index]),
                        borderWidth: 2,
                    };
                }),
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: true, position: "top" },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: "Valuation",
                            font: { size: 21 },
                        },
                    },
                    x: {
                        title: {
                            display: true,
                            text: "Date",
                            font: { size: 21 },
                        },
                    },
                },
            },
        };
    }

    get totalValuation() {
        return formatMonetary(this.props.stats.valuation, { currencyId: this.props.stats.currencyId, humanReadable: true });
    }

    get yourValuation() {
        return formatMonetary(this.props.stats.yourValuation, { currencyId: this.props.stats.currencyId, humanReadable: true });
    }

    get ownership() {
        return formatPercentage(this.props.stats.ownership);
    }

    get votingRights() {
        return formatPercentage(this.props.stats.votingRights);
    }
}

registry.category("public_components").add("equity.ValuationChart", ValuationChart);
