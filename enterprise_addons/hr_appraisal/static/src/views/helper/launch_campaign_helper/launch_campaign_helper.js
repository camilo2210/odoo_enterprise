import { user } from "@web/core/user";

export async function canLaunchCampaign(orm) {
    if (await user.hasGroup("hr_appraisal.group_hr_appraisal_user")) {
        return true;
    }
    const subordinateCount = await orm.searchCount("hr.employee", [
        ["parent_id.user_id", "=", user.userId],
        ["company_id", "in", user.activeCompanies.map((c) => c.id)],
    ]);
    return subordinateCount > 0;
}

export function removeLaunchButton(headerButtons) {
    if (!headerButtons) {
        return headerButtons;
    }
    return headerButtons.filter(
        (btn) => !btn.className?.includes("o_appraisal_launch_campaign_button")
    );
}
