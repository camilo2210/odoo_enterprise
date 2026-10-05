import { useChart } from "@web/core/utils/chart_hook";
import { registry } from "@web/core/registry";
import { getColor } from "@web/core/colors/colors";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, useProps } from "@odoo/owl";
import { cookie } from "@web/core/browser/cookie";

export class CommissionGraphField extends Component {
    static template = "sale_commission.GraphField";

    props = useProps(standardFieldProps);

    chart = useChart(() => {
        this.data = JSON.parse(this.props.record.data[this.props.name]);
        return this.getLineChartConfig();
    });

    /**
     * Find the greatest common divisor of two number (Euclidean algorithm)
     * @param {*} a integer, first number
     * @param {*} b integer, second one
     * @returns the greatest common divisor
     */
    GCD(a, b) {
        a = Math.abs(a);
        b = Math.abs(b);
        if (a < b) {
            return this.GCD(b, a);
        }
        if (b == 0) {
            return a;
        }
        return this.GCD(b, a % b);
    }

    getLineChartConfig() {
        const labels = this.data.values.map(function (pt) {
            return pt.x;
        });

        let gcd = 0;
        this.data.values.forEach((v) => {
            gcd = this.GCD(v.x, gcd);
        });

        const color10 = getColor(3, cookie.get("color_scheme"), "odoo");
        const currency = this.data.currency;
        return {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        color10,
                        data: this.data.values,
                        fill: "start",
                        borderWidth: 2,
                    },
                ],
            },
            options: {
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        enabled: true,
                        intersect: false,
                        position: "nearest",
                        caretSize: 0,
                    },
                },
                scales: {
                    x: {
                        type: "linear",
                        ticks: {
                            stepSize: gcd,
                            callback: function (value, index, ticks) {
                                return value + "%";
                            },
                        },
                    },
                    y: {
                        type: "linear",
                        ticks: {
                            callback: function (value, index, ticks) {
                                return value + currency;
                            },
                        },
                    },
                },
                elements: {
                    line: {
                        tension: 0.000001,
                    },
                },
            },
        };
    }
}

export const commissionGraphField = {
    component: CommissionGraphField,
    supportedTypes: ["text"],
};

registry.category("fields").add("commission_graph", commissionGraphField);
