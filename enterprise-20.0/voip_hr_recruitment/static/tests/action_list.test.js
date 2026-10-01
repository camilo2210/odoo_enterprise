import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { onRpc } from "@web/../tests/web_test_helpers";
import { describe, test } from "@odoo/hoot";
import { openRecentContactSearch } from "@voip/../tests/voip_test_helpers";
import { setupVoipHrRecruitmentTests } from "@voip_hr_recruitment/../tests/voip_hr_recruitment_test_helpers";

describe.current.tags("desktop");
setupVoipHrRecruitmentTests();

test("ApplicantButton is hidden when user doesn't have hr_recruitment.group_hr_recruitment_interviewer group", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", () => false);
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:text('Test Partner')");
    await contains("button.o-voip-ActionButton[title='Go to']");
    await contains("button.o-voip-ActionButton[title='Create']", { count: 0 });
});

test("ApplicantButton is shown when user has hr_recruitment.group_hr_recruitment_interviewer group", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "hr_recruitment.group_hr_recruitment_interviewer";
    });
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:text('Test Partner')");
    await click("button.o-voip-ActionButton[title='Create']");
    await contains("span.o-dropdown-item i[data-icon='work']");
    await contains("span.o-dropdown-item span:contains('Applicant')");
});

test("ApplicantButton is shown with title 'View applicant' and icon 'luggage' when user has hr_recruitment.group_hr_recruitment_interviewer group", async () => {
    const pyEnv = await startServer();
    const applicantId = pyEnv["hr.applicant"].create({
        partner_name: "Test Applicant",
        partner_id: 1,
    });
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
        applicant_ids: [applicantId],
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "hr_recruitment.group_hr_recruitment_interviewer";
    });
    await start();
    await openRecentContactSearch("Test Partner");
    // voipName resolves to the linked applicant's partner_name (see res_partner_model_patch),
    // so the entry is searchable by the partner's complete_name but displays the applicant name.
    await click(".o-voip-TabEntry .o-voip-TabEntry-title:text('Test Applicant')");
    await click(".o-voip-TabEntry .o-voip-highlighted-letter:text('Test Partner')");
    await click("button.o-voip-ActionButton[title='Go to']");
    await contains("span.o-dropdown-item i[data-icon='work']");
    await contains("span.o-dropdown-item span:contains('Applicant')");
});
