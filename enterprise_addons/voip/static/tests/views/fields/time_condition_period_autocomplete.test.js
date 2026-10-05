/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { allowTranslations } from "@web/../tests/web_test_helpers";
import {
    formatRanges,
    parseRanges,
    TimeConditionPeriodAutocomplete,
} from "@voip/views/fields/time_condition_period_autocomplete/time_condition_period_autocomplete";
import { TimeConditionPeriodsField } from "@voip/views/fields/time_condition_periods_field";

test.tags("headless");

beforeEach(() => {
    allowTranslations();
});

describe("Time Condition period autocomplete", () => {
    test("parses individual values and compact ranges", () => {
        expect([...parseRanges("1-3,5,7", 7)]).toEqual([1, 2, 3, 5, 7]);
        expect([...parseRanges("2,2,3", 7)]).toEqual([2, 3]);
        expect([...parseRanges("0,8,4-2", 7)]).toEqual([]);
    });

    test("formats consecutive values as compact ranges", () => {
        expect(formatRanges(new Set([7, 2, 3, 1, 5]))).toBe("1-3,5,7");
        expect(formatRanges(new Set())).toBe("");
    });

    test("select all writes every selector value as one range", () => {
        let value;
        TimeConditionPeriodAutocomplete.prototype.selectAll.call({
            config: { labels: Array(7).fill("") },
            update(selectedValues) {
                value = formatRanges(selectedValues);
            },
        });
        expect(value).toBe("1-7");
    });

    test("clear all writes an empty selection", () => {
        let value = "1-7";
        TimeConditionPeriodAutocomplete.prototype.clearAll.call({
            update(selectedValues) {
                value = formatRanges(selectedValues);
            },
        });
        expect(value).toBe("");
    });

    test("uses the selected period type in the creation dialog title", async () => {
        for (const [context, expectedContext, expectedTitle] of [
            ["{'default_mode': 'open'}", { default_mode: "open" }, "Create an open period"],
            [
                "{'default_mode': 'closed', 'default_month_days': '', 'default_months': ''}",
                {
                    default_mode: "closed",
                    default_month_days: "",
                    default_months: "",
                },
                "Create a closed period",
            ],
        ]) {
            let dialog;
            await TimeConditionPeriodsField.prototype.onAdd.call(
                {
                    props: { context: {} },
                    _openRecord(params) {
                        dialog = params;
                    },
                },
                { context }
            );
            expect(dialog.context).toEqual(expectedContext);
            expect(String(dialog.title)).toBe(expectedTitle);
        }
    });
});
