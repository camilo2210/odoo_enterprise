import { expect, test } from "@odoo/hoot";
import { click, press } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, Plugin, providePlugins, signal, xml, useProps } from "@odoo/owl";
import { mountWithCleanup, defineModels } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

import { AccountReportLineCellEditable } from "@account_reports/components/account_report/line_cell_editable/line_cell_editable";

// Due to dependency with mail module, we have to define their models for our tests.
defineModels(mailModels);

class AccountReportController extends Plugin {
    options = {};
    scheduleClassUpdate = () => {};
}

class AccountReportLineCellEditableTestWrapper extends Component {
    static template = xml`<AccountReportLineCellEditable t-props="this.props"/>`;
    static components = { AccountReportLineCellEditable };

    props = useProps([ "cell", "line", "cellIndex" ]);
    setup() {
        providePlugins([AccountReportController]);
    }
}

test("can unformat a value when focus and format when blur", async () => {
    await mountWithCleanup(AccountReportLineCellEditableTestWrapper, {
        props: {
            cell: {
                name: signal("5,702.22"),
                no_format: signal(5702.22),
                edit_popup_data: signal("{}"),
                figure_type: signal("float"),
            },
            cellIndex: 0,
            line: {},
        },
    });

    expect(".o_input").toHaveValue("5,702.22");
    await click("[data-icon='edit']");
    await animationFrame();
    expect(".o_input").toHaveValue("5702.22");
    await press("Enter");
    await animationFrame();
    expect(".o_input").toHaveValue("5,702.22");
});

test("can display boolean value", async () => {
    await mountWithCleanup(AccountReportLineCellEditableTestWrapper, {
        props: {
            cell: {
                name: signal("No"),
                no_format: signal(0),
                edit_popup_data: signal("{}"),
                figure_type: signal("boolean"),
            },
            cellIndex: 0,
            line: {},
        },
    });
    expect(".o_input").toHaveValue("No");
});

test("can display a date value", async () => {
    await mountWithCleanup(AccountReportLineCellEditableTestWrapper, {
        props: {
            cell: {
                name: signal("2026-02-12T00:00:00.000+01:00"),
                no_format: signal("2026-02-12T00:00:00.000+01:00"),
                edit_popup_data: signal("{}"),
                figure_type: signal("date"),
            },
            cellIndex: 0,
            line: {},
        },
    });
    expect(".o_input").toHaveValue("02/12/2026");
});

test("can display a datetime value in UTC", async () => {
    await mountWithCleanup(AccountReportLineCellEditableTestWrapper, {
        props: {
            cell: {
                name: signal("2026-02-12T10:00:00.000Z"),
                no_format: signal("2026-02-12T10:00:00.000Z"),
                edit_popup_data: signal("{}"),
                figure_type: signal("datetime"),
            },
            cellIndex: 0,
            line: {},
        },
    });
    expect(".o_input").toHaveValue("02/12/2026 10:00:00");
});

test("can display a datetime value in UTC +1 and datetime in UTC +1", async () => {
    AccountReportController.prototype.context = { tz: "Europe/Brussels" };
    await mountWithCleanup(AccountReportLineCellEditableTestWrapper, {
        props: {
            cell: {
                name: signal("2026-02-12T10:00:00.000+01:00"),
                no_format: signal("2026-02-12T10:00:00.000+01:00"),
                edit_popup_data: signal("{}"),
                figure_type: signal("datetime"),
            },
            cellIndex: 0,
            line: {},
        },
    });
    expect(".o_input").toHaveValue("02/12/2026 10:00:00");
});

test("can display a datetime value in UTC +1 but datetime in UTC", async () => {
    AccountReportController.prototype.context = { tz: "Europe/Brussels" };
    await mountWithCleanup(AccountReportLineCellEditableTestWrapper, {
        props: {
            cell: {
                name: signal("2026-02-12T10:00:00.000Z"),
                no_format: signal("2026-02-12T10:00:00.000Z"),
                edit_popup_data: signal("{}"),
                figure_type: signal("datetime"),
            },
            cellIndex: 0,
            line: {},
        },
    });
    expect(".o_input").toHaveValue("02/12/2026 11:00:00");
});
