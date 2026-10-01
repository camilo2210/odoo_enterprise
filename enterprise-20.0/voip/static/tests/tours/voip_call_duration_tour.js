import { registry } from "@web/core/registry";

const TEST_CONTACT_NAME = "VOIP Duration Tour Contact";
const COUNT_MEASURE = "Count";
const DURATION_MEASURE = "Duration";
const EXPECTED_DURATION = "2m 3s";
const EXPECTED_DURATION_SUM = "2m 13s";

function selectReportMeasure(viewName, measureButtonSelector, measureName) {
    return [
        {
            content: `Open the ${viewName} measure menu`,
            trigger: measureButtonSelector,
            run: "click",
        },
        {
            content: `Check ${viewName} defaults to count`,
            trigger: `.o-dropdown--menu .o_menu_item.selected:text("${COUNT_MEASURE}")`,
        },
        {
            content: `Select the duration ${viewName} measure`,
            trigger: `.o-dropdown--menu .o_menu_item:text("${measureName}")`,
            run: "click",
        },
    ];
}

registry.category("web_tour.tours").add("voip_call_duration_views_tour", {
    steps: () => [
        {
            content: "Check the list view duration",
            trigger: `table.o_list_table tr:contains("${TEST_CONTACT_NAME}") td:text(${EXPECTED_DURATION})`,
        },
        {
            content: "Switch to kanban view",
            trigger: "button.o_switch_view.o_kanban",
            run: "click",
        },
        {
            content: "Check the kanban view duration",
            trigger: `.o_kanban_record:contains("${TEST_CONTACT_NAME}") footer .ms-1:text("${EXPECTED_DURATION}")`,
        },
        {
            content: "Open the call form",
            trigger: `.o_kanban_record:contains("${TEST_CONTACT_NAME}")`,
            run: "click",
        },
        {
            content: "Check the form view duration",
            trigger: `.o_form_view .o_field_voip_simple_datetime:contains("${EXPECTED_DURATION}")`,
        },
        {
            content: "Switch back to multi-record views",
            trigger: ".o_back_button > a",
            run: "click",
        },
        {
            content: "Switch to pivot view",
            trigger: "button.o_switch_view.o_pivot",
            run: "click",
        },
        ...selectReportMeasure("pivot", ".o_pivot_buttons .o_report_measures", DURATION_MEASURE),
        {
            content: "Close the pivot measure menu",
            trigger: ".o_pivot_buttons .o_report_measures",
            run: "click",
        },
        {
            content: "Check the pivot view duration",
            trigger: `.o_pivot_cell_value .o_value:text("${EXPECTED_DURATION_SUM}")`,
        },
        {
            content: "Switch to graph view",
            trigger: "button.o_switch_view.o_graph",
            run: "click",
        },
        ...selectReportMeasure("graph", ".o_graph_renderer .o_report_measures", DURATION_MEASURE),
        {
            content: "Wait for the duration graph measure",
            trigger: `.o_graph_renderer .o_report_measures:text("${DURATION_MEASURE}")`,
        },
        {
            content: "Show the graph duration tooltip",
            trigger: ".o_graph_canvas_container canvas",
            async run() {
                const chart = Chart.getChart(this.anchor);
                const position = chart.getDatasetMeta(0).data[0].getCenterPoint(true);
                if (document.querySelector(".o_graph_custom_tooltip")) {
                    return;
                }
                const dataPoints = chart.data.datasets.flatMap((dataset, i) => {
                    const raw = dataset.data[0];
                    return raw === undefined ? [] : [{ datasetIndex: i, dataIndex: 0, raw }];
                });
                chart.config.options.plugins.tooltip.external({
                    chart,
                    tooltip: { opacity: 1, x: position.x, y: position.y, dataPoints },
                });
            },
        },
        {
            content: "Check the graph view duration tooltip",
            trigger: `.o_graph_custom_tooltip .o_value:text("${EXPECTED_DURATION_SUM}")`,
        },
    ],
});
