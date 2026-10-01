import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, Plugin, providePlugins, proxy, signal, usePlugin, xml } from "@odoo/owl";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";

// Due to dependency with mail module, we have to define their models for our tests.
defineMailModels();

test("can change the date filter by editing textually", async () => {
    const date = proxy({
        period_type: "month",
        date_to: "2019-03-31",
        date_from: "2019-03-01",
    });

    class AccountReportController extends Plugin {
        filters = { show_period_comparison: false };
        userGroups = {};
        cachedUserGroups = {};
        cachedFilterOptions = () => ({
            available_horizontal_groups: [],
            available_variants: [],
            companies: [],
            date: date,
            filter_date: {
                range_mode: true,
                filters: {
                    month: {
                        key: "month",
                        start_day: 1,
                        start_month: 1,
                        months_per_period: 1,
                    },
                    quarter: {
                        key: "quarter",
                        start_day: 1,
                        start_month: 1,
                        months_per_period: 3,
                    },
                    year: {
                        key: "year",
                        start_day: 1,
                        start_month: 1,
                        months_per_period: 12,
                        custom_ranges: [
                            ["2022-01-01", "2022-06-30", "FY 2022_1"],
                            ["2022-07-01", "2022-12-31", "FY 2022_2"],
                        ],
                    },
                },
            },
            rounding_unit: "decimals",
            rounding_unit_names: {
                decimals: ".$",
            },
        });
        reload = (optionPath, newOptions) => {
            expect.step(`reload ${optionPath} to ${newOptions}`);
        };
        updateOption = (option, value) => {
            if (option === "date") {
                expect.step(
                    `update option ${option} -> period_type: ${value.period_type} date_from: ${value.date_from} date_to: ${value.date_to}`
                );

                date.period_type = value.period_type;
                date.date_from = value.date_from;
                date.date_to = value.date_to;
            }
        };
        getCacheKey = (sectionsSourceId, reportId) => `${sectionsSourceId}_${reportId}`;
        loadingCallNumberByCacheKey = new Proxy(
            {},
            {
                get(target, name) {
                    return name in target ? target[name] : 0;
                },
                set(target, name, newValue) {
                    target[name] = newValue;
                    return true;
                },
            }
        );
        revision = 0;
        template = () => "account_reports.AccountReportFiltersCustomizable";
        component = () => AccountReportFilters;
    }

    class AccountReportTestWrapper extends Component {
        static template = xml`<AccountReportFilters/>`;
        static components = { AccountReportFilters };

        setup() {
            providePlugins([AccountReportController]);
        }
    }

    await mountWithCleanup(AccountReportTestWrapper);
    // Default date = 2019-03-11

    // Open Date Filter dropdown
    await contains("#filter_date > button.o-dropdown").click();

    // Click the Month input when selected
    await contains(".date_filter_month.selected .input_current_date").click();
    // Edit the month by changing the text (+14 months)
    await contains(".date_filter_month .input_current_date:not([readonly])").edit("May 2020", {
        confirm: "tab",
    });
    // Click the Month input when selected
    await contains(".date_filter_month.selected .input_current_date").click();
    // Edit the month by changing the text (-10 months)
    await contains(".date_filter_month .input_current_date:not([readonly])").edit("May 2018", {
        confirm: "tab",
    });
    // Click the Month input when selected
    await contains(".date_filter_month.selected .input_current_date").click();
    // Edit the month by changing the text to something invalid
    await contains(".date_filter_month .input_current_date:not([readonly])").edit("Invalid Month", {
        confirm: "tab",
    });

    // Select the Quarter filter
    await contains(".date_filter_quarter").click();

    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text (+5 quarters)
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit(
        "Apr - Jun 2020",
        { confirm: "tab" }
    );
    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text (-3 quarters)
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit(
        "Apr - Jun 2018",
        { confirm: "tab" }
    );
    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text (invalid quarter, -4 quarters)
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit(
        "Random - Feb 2018",
        { confirm: "tab" }
    );
    // Click the Quarter input when selected
    await contains(".date_filter_quarter.selected .input_current_date").click();
    // Edit the quarter by changing the text to something invalid
    await contains(".date_filter_quarter .input_current_date:not([readonly])").edit(
        "Invalid Quarter",
        { confirm: "tab" }
    );

    // Select the Year filter
    await contains(".date_filter_year").click();

    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text (+2 years)
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("2021", {
        confirm: "tab",
    });
    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text (-1 year)
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("2018", {
        confirm: "tab",
    });
    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text to something invalid
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("Invalid Year", {
        confirm: "tab",
    });

    // Check for custom ranges

    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text to something invalid
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("FY 2022_1");
    // Click the Year input when selected
    await contains(".date_filter_year.selected .input_current_date").click();
    // Edit the year by changing the text to something invalid
    await contains(".date_filter_year .input_current_date:not([readonly])").edit("FY 2022_2");

    expect.verifySteps([
        // Set the period to May 2020
        "update option date -> period_type: month date_from: 2020-05-01 date_to: 2020-05-31",

        // Set the period to May 2018
        "update option date -> period_type: month date_from: 2018-05-01 date_to: 2018-05-31",

        // Keep the month the same after entering an invalid value

        // Switch to Quarter
        "update option date -> period_type: quarter date_from: 2019-01-01 date_to: 2019-03-31",

        // Set the quarter to +5 quarters
        "update option date -> period_type: quarter date_from: 2020-04-01 date_to: 2020-06-30",

        // Set the quarter to -3 quarters
        "update option date -> period_type: quarter date_from: 2018-04-01 date_to: 2018-06-30",

        // Set the quarter to -4 quarters
        "update option date -> period_type: quarter date_from: 2018-01-01 date_to: 2018-03-31",

        // Keep the quarter the same after entering an invalid value

        // Switch to Year
        "update option date -> period_type: year date_from: 2019-01-01 date_to: 2019-12-31",

        // // Set the year to +2 years
        "update option date -> period_type: year date_from: 2021-01-01 date_to: 2021-12-31",

        // // Set the year to -1 year
        "update option date -> period_type: year date_from: 2018-01-01 date_to: 2018-12-31",

        // Keep the year the same after entering an invalid value

        //Custom range FY 2022_1
        "update option date -> period_type: year date_from: 2022-01-01 date_to: 2022-06-30",
        //Custom range FY 2022_2
        "update option date -> period_type: year date_from: 2022-07-01 date_to: 2022-12-31",
    ]);
});

test("date filter is reset when the report changes", async () => {
    const filterOptions = {
        report_id: 1,
        available_horizontal_groups: [],
        available_variants: [],
        date: {
            period_type: "month",
            date_to: "2026-06-30",
            date_from: "2026-06-01",
        },
        filter_date: {
            range_mode: false,
            filters: {
                month: { key: "month", start_day: 1, start_month: 1, months_per_period: 1 },
            },
        },
        rounding_unit: "decimals",
        rounding_unit_names: { decimals: ".$" },
    };

    class AccountReportController extends Plugin {
        filters = { show_period_comparison: false };
        cachedUserGroups = {};
        cachedFilterOptions = signal(proxy(filterOptions));
        reload = () => {};
        updateOption = () => {};
        getCacheKey = () => "key";
        loadingCallNumberByCacheKey = {};

        template = () => "account_reports.AccountReportFiltersCustomizable";
        component = () => AccountReportFilters;
    }

    class AccountReportTestWrapper extends Component {
        static template = xml`<AccountReportFilters/>`;
        static components = { AccountReportFilters };

        setup() {
            providePlugins([AccountReportController]);
            this.controller = usePlugin(AccountReportController);
        }
    }
    const filters = await mountWithCleanup(AccountReportTestWrapper);

    // Move report 1 date filter March 2024 -> April 2024.
    await contains("#filter_date > button.o-dropdown").click();
    expect(".date_filter_month .input_current_date").toHaveValue("June 2026");
    await contains(".date_filter_month .btn_next_date").click();
    expect(".date_filter_month .input_current_date").toHaveValue("July 2026");

    // Switching to another report must reset the date filter to that report's date.
    filters.controller.cachedFilterOptions().report_id = 2;
    await animationFrame();
    expect(".date_filter_month .input_current_date").toHaveValue("June 2026");
});
