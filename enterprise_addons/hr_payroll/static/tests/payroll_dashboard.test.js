import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import { waitUntil } from "@odoo/hoot-dom";
import { defineModels, fields, models, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { hrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers";
import PayrollDashboardComponent, { STORAGE_KEY_PREFIX } from "@hr_payroll/components/dashboard/payroll_dashboard";

class HrPayrollWarning extends models.Model {
    _name = "hr.payroll.warning";
    name = fields.Char();
    _records = [];
}

describe.current.tags("desktop");
defineModels({ ...hrPayrollModels, HrPayrollWarning });

function seedCache(cachedWarnings) {
    const key = `${STORAGE_KEY_PREFIX}_${user.activeCompany?.id}_${user.userId}`;
    browser.localStorage.setItem(key, JSON.stringify(cachedWarnings));
}

function warningsOnDate(dashboard, date) {
    return dashboard.state.warnings.filter((w) => w.warning_date === date);
}

function mountDashboard() {
    return mountWithCleanup(PayrollDashboardComponent, {
        props: { action: {}, actionId: 1, className: "" },
    });
}

function mockWarningStream(cards) {
    const lines = cards.map((warning) => JSON.stringify({ type: "card", warning }));
    lines.push(JSON.stringify({ type: "done" }));
    const body = lines.map((line) => line + "\n").join("");
    onRpc("/hr_payroll/dashboard/warnings", () => new Response(body));
}

beforeEach(() => {
    mockDate("2026-06-25 09:00:00", +0);
    browser.localStorage.clear();
});

test("corrections from one visit persist to the next: valid cards paint instantly, resolved ones don't reappear", async () => {
    mockWarningStream([
        {
            id: 3,
            key: "monthly_3",
            name: "Payrun: Jun 2026",
            description: "",
            color_class: "info",
            button_name: "Start Pay Run",
            warning_date: "2026-06-30",
            count: 0,
        },
        {
            id: 42,
            key: "monthly_42",
            name: "New Warning",
            description: "",
            color_class: "warning",
            button_name: "Review Records",
            warning_date: "2026-06-29",
            count: 1,
        },
    ]);

    let dashboardDataDeferred = null;
    onRpc("hr.payroll.warning", "get_payroll_dashboard_data", () => {
        if (dashboardDataDeferred) {
            return dashboardDataDeferred;
        }
        return { closing_dates_data: [], mandatory_config_id: false, warning_ids: [3, 6, 42] };
    });

    const firstVisit = await mountDashboard();
    await animationFrame();
    await waitUntil(() => !firstVisit.state.isRecomputing);

    expect(warningsOnDate(firstVisit, "2026-06-30")).toHaveLength(1);
    expect(warningsOnDate(firstVisit, "2026-06-29")).toHaveLength(1);
    expect(firstVisit.state.warnings.find((w) => w.id === 6)).toBe(undefined);

    // Freeze the second mount before its ORM call resolves, so the live stream
    // can't start yet: this lets us assert on the cache-only state below,
    // before it would otherwise get overwritten by fresh stream data.
    let resolveDashboardData;
    dashboardDataDeferred = new Promise((resolve) => {
        resolveDashboardData = resolve;
    });
    const secondVisit = await mountDashboard();
    await animationFrame();

    const instantPlaceholder = secondVisit.state.warnings.find((w) => w.id === 3);
    expect(instantPlaceholder).not.toBe(undefined);
    expect(instantPlaceholder.is_loading).toBe(true);
    expect(instantPlaceholder.warning_date).toBe("2026-06-30");
    expect(secondVisit.state.warnings.find((w) => w.id === 6)).toBe(undefined);

    // Let the pending call settle so the stream can finish before the component
    // gets torn down; nothing to assert on here, this is cleanup only.
    resolveDashboardData({ closing_dates_data: [], mandatory_config_id: false, warning_ids: [3, 6, 42] });
    await animationFrame();
});

test("two cards sharing the same warning id but a different schedule don't collide once cached", async () => {
    // Same warning split into two cards because it applies to employees on
    // different pay schedules (e.g. l10n_hk's monthly vs weekly structure types),
    // with both schedules happening to land on the same warning_date.
    mockWarningStream([
        {
            id: 175,
            key: "monthly_175",
            name: "Untrusted Bank Accounts",
            description: "It will not possible to pay your employees",
            color_class: "info",
            button_name: "Review Bank Accounts",
            warning_date: "2026-06-25",
            count: 1,
        },
        {
            id: 175,
            key: "weekly_175",
            name: "Untrusted Bank Accounts",
            description: "It will not possible to pay your employees",
            color_class: "info",
            button_name: "Review Bank Accounts",
            warning_date: "2026-06-25",
            count: 2,
        },
    ]);

    let dashboardDataDeferred = null;
    onRpc("hr.payroll.warning", "get_payroll_dashboard_data", () => {
        if (dashboardDataDeferred) {
            return dashboardDataDeferred;
        }
        return { closing_dates_data: [], mandatory_config_id: false, warning_ids: [175] };
    });

    const firstVisit = await mountDashboard();
    await waitUntil(() => !firstVisit.state.isRecomputing);

    const firstVisitCards = firstVisit.state.warnings.filter((w) => w.id === 175);
    expect(firstVisitCards).toHaveLength(2);
    expect(new Set(firstVisitCards.map((w) => w.key)).size).toBe(2);

    // Freeze the second ORM call to only assert cached data
    let resolveDashboardData;
    dashboardDataDeferred = new Promise((resolve) => {
        resolveDashboardData = resolve;
    });
    const secondVisit = await mountDashboard();
    // No crash should happen on t-foreach
    await animationFrame();

    // Ensure that both warning are still there with same id but different key
    const cachedPlaceholders = secondVisit.state.warnings.filter((w) => w.id === 175);
    expect(cachedPlaceholders).toHaveLength(2);
    expect(new Set(cachedPlaceholders.map((w) => w.key)).size).toBe(2);

    // Let the pending call settle so the stream can finish before the component
    // gets torn down; nothing to assert on here, this is cleanup only.
    resolveDashboardData({ closing_dates_data: [], mandatory_config_id: false, warning_ids: [175] });
    await animationFrame();
});

test("a malformed or outdated cache entry is discarded instead of being rendered", async () => {
    seedCache([
        { id: 8, name: "Valid Cached Warning", button_name: "Review", warning_date: "2026-06-27" },
        { id: 9, name: "Missing warning_date" }, // old/corrupted shape
        { name: "Missing id entirely", button_name: "Review", warning_date: "2026-06-27" },
        "not even an object",
    ]);
    onRpc("hr.payroll.warning", "get_payroll_dashboard_data", () => ({
        closing_dates_data: [],
        mandatory_config_id: false,
        warning_ids: [8],
    }));
    mockWarningStream([
        {
            id: 8,
            key: "monthly_8",
            name: "Valid Cached Warning",
            description: "",
            color_class: "info",
            button_name: "Review",
            warning_date: "2026-06-27",
            count: 1,
        },
    ]);

    const dashboard = await mountDashboard();
    await animationFrame();

    expect(dashboard.state.warnings).toHaveLength(1);
    expect(dashboard.state.warnings[0].id).toBe(8);
});

test("a failing warning is isolated as its own card without blocking the others, and is cached like any other card", async () => {
    let dashboardDataDeferred = null;
    onRpc("hr.payroll.warning", "get_payroll_dashboard_data", () => {
        if (dashboardDataDeferred) {
            return dashboardDataDeferred;
        }
        return { closing_dates_data: [], mandatory_config_id: false, warning_ids: [31, 7] };
    });
    mockWarningStream([
        {
            id: 31,
            key: "error_31",
            name: "Broken Warning",
            description: "This warning could not be computed.",
            color_class: "danger",
            is_error: true,
            warning_date: "2026-06-25",
            button_name: "See details",
            button_action: { type: "ir.actions.client", tag: "display_exception", params: { message: "Test" } },
        },
        {
            id: 7,
            key: "monthly_7",
            name: "Configure your payslip layout",
            description: "",
            color_class: "info",
            button_name: "Configure",
            warning_date: "2026-01-01",
            count: 0,
        },
    ]);

    const firstVisit = await mountDashboard();
    await animationFrame();
    await waitUntil(() => !firstVisit.state.isRecomputing);

    const errorCard = firstVisit.state.warnings.find((w) => w.id === 31);
    const okCard = firstVisit.state.warnings.find((w) => w.id === 7);

    expect(errorCard).not.toBe(undefined);
    expect(errorCard.color_class).toBe("danger");
    expect(errorCard.button_action.tag).toBe("display_exception");

    expect(okCard).not.toBe(undefined);
    expect(okCard.is_loading).toBe(false);

    // Freeze the second mount before its ORM call resolves, so the live stream
    // can't start yet: this lets us assert on the cache-only state below,
    // before it would otherwise get overwritten by fresh stream data.
    let resolveDashboardData;
    dashboardDataDeferred = new Promise((resolve) => {
        resolveDashboardData = resolve;
    });
    const secondVisit = await mountDashboard();
    await animationFrame();

    const cachedErrorPlaceholder = secondVisit.state.warnings.find((w) => w.id === 31);
    expect(cachedErrorPlaceholder).not.toBe(undefined);
    expect(cachedErrorPlaceholder.is_loading).toBe(true);

    // Let the pending call settle so the stream can finish before the component
    // gets torn down; nothing to assert on here, this is cleanup only.
    resolveDashboardData({ closing_dates_data: [], mandatory_config_id: false, warning_ids: [31, 7] });
    await animationFrame();
});

test("groupedWarnings removes a month group entirely once all its warnings are removed", async () => {
    onRpc("hr.payroll.warning", "get_payroll_dashboard_data", () => ({
        closing_dates_data: [],
        mandatory_config_id: false,
        warning_ids: [],
    }));
    mockWarningStream([]);

    const dashboard = await mountDashboard();
    await animationFrame();

    dashboard.mergeWarning({ id: 1, key: "monthly_1", warning_date: "2026-06-10" });
    expect(dashboard.groupedWarnings).toHaveLength(1);

    dashboard.removeWarning(dashboard.state.warnings[0]);
    expect(dashboard.groupedWarnings).toHaveLength(0);
});
