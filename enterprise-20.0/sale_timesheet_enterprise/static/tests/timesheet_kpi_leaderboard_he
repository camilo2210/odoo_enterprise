import { expect } from "@odoo/hoot";
import { queryText } from "@odoo/hoot-dom";

export async function checkKpiHeader(showLeaderboard = true) {
    expect("div[name=timesheet_kpi_leaderboard_header]").toHaveCount(1, {
        message: "The KPI header should be visible",
    });

    expect("div[name=worked_time_kpi]").toHaveCount(1, {
        message: "The total time worked KPI should be visible",
    });
    expect("div[name=billable_time_kpi]").toHaveCount(1, {
        message: "The billable time KPI should be visible",
    });
    expect("div[name=billing_rate_kpi]").toHaveCount(1, {
        message: "The billing rate KPI should be visible",
    });
    expect("div[name=open_timesheet_assistant]").toHaveCount(1, {
        message: "The button to open the timesheet assistant should be visible",
    });

    expect("div[name=timesheet_kpi_leaderboard_header] .text-uppercase span:eq(0)").toHaveCount(1, {
        message: "The short month name should be displayed",
    });
    expect("div[name=timesheet_kpi_leaderboard_header] .text-uppercase span:eq(1)").toHaveCount(1, {
        message: "The year should be displayed",
    });

    expect("div[name=billable_time_kpi] > span > span:eq(0)").toHaveCount(1, {
        message: "The billable time KPI should show the actual value",
    });
    expect("div[name=billable_time_kpi] > span > span.small").toHaveCount(1, {
        message: "The billable time KPI should show the target value",
    });

    const billingRateText = queryText("div[name=billing_rate_kpi] > span");
    const billingRate = parseFloat(billingRateText);
    expect("div[name=billing_rate_kpi] > span").toHaveClass(
        billingRate >= 100 ? "text-success" : "text-danger",
        {
            message: "The billing rate KPI should be green if >= 100%, else red",
        }
    );

    if (showLeaderboard) {
        expect(".o_timesheet_leaderboard").toHaveCount(1, {
            message: "The leaderboard should be visible if user's company has the feature on",
        });
    } else {
        expect("div.o_timesheet_leaderboard").toHaveCount(0, {
            message:
                "The leaderboard should not be visible if user's company does not have the feature on",
        });
    }

    expect.verifySteps(["get_kpi_data", "get_timesheet_ranking_data"], {
        ignoreOrder: true,
        message: "The services should be called only once",
    });
}
