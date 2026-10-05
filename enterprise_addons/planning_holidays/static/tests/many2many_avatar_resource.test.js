import { createPublicEmployee } from "@hr/../tests/hr_test_helpers";

import { describe, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { contains, makeMockServer, mountView } from "@web/../tests/web_test_helpers";
import { definePlanningHolidaysModels } from "./planning_holidays_test_helpers";

const { DateTime } = luxon;

describe.current.tags("desktop");
definePlanningHolidaysModels();

test("many2many_avatar_resource widget in list view with time-off idle", async () => {
    /* 1. Create data
           two type of records tested:
            - 2 planning slots linked to a human resource not linked to a user:
              the hr employee status should be displayed in avatar card popover
            - 2 planning slots linked to a human resource linked to a user:
              the im status of the user should be displayed in avatar card popover
    */

    const { env } = await makeMockServer();

    // partners
    const [lucindaPartnerId, cardenioPartnerID] = env["res.partner"].create([
        { name: "Lucinda" },
        { name: "Cardenio" },
    ]);

    // Users
    const [lucindaUserId, cardenioUserId] = env["res.users"].create([
        { name: "Lucinda", partner_id: lucindaPartnerId, im_status: "online" },
        { name: "Cardenio", partner_id: cardenioPartnerID, im_status: "away" },
    ]);

    // Resources
    const [resDoro, resFer, resluci, resCar] = env["resource.resource"].create([
        {
            name: "Dorothea",
            resource_type: "user",
        },
        {
            name: "Fernando",
            resource_type: "user",

        },
        {
            name: "Lucinda",
            resource_type: "user",
            user_id: lucindaUserId,
        },
        {
            name: "Cardenio",
            resource_type: "user",
            user_id: cardenioUserId,
        },
    ]);

    // Employees
    const employeeDorotheaData = {
        name: "Dorothea",
        hr_icon_display: "presence_holiday_present",
        resource_id: resDoro,
        show_hr_icon_display: true,
    };
    const employeeFernandoData = {
        name: "Fernando",
        hr_icon_display: "presence_holiday_absent",
        resource_id: resFer,
        show_hr_icon_display: true,
    };
    const employeeLucindaData = {
        name: "Lucinda",
        resource_id: resluci,
        user_id: lucindaUserId,
        user_partner_id: lucindaPartnerId,
        leave_date_to: DateTime.now().plus({ days: 3 }).toISODate(),
    };
    const employeeCardenioData = {
        name: "Cardenio",
        resource_id: resCar,
        user_id: cardenioUserId,
        user_partner_id: cardenioPartnerID,
        leave_date_to: DateTime.now().plus({ days: 3 }).toISODate(),
    };
    createPublicEmployee(env, [
        employeeDorotheaData,
        employeeFernandoData,
        employeeLucindaData,
        employeeCardenioData,
    ]);
    // FIXME: Manually trigger recomputation of related fields
    env["resource.resource"]._applyComputesAndValidate();
    // Planning slots
    env["planning.slot"].create([
        {
            display_name: "Planning slot Dorothea",
            resource_ids: [resDoro],
        },
        {
            display_name: "Planning slot Fernando",
            resource_ids: [resFer],
        },
        {
            display_name: "Planning Slot Lucinda",
            resource_ids: [resluci],
        },
        {
            display_name: "Planning Slot Cardenio",
            resource_ids: [resCar],
            user_ids: [cardenioUserId],
        },
    ]);
    await mountView({
        type: "list",
        resModel: "planning.slot",
        arch: `
        <list>
            <field name="display_name"/>
            <field name="resource_ids" widget="many2many_avatar_resource"/>
        </list>`,
    });

    // 1. Clicking on human resource's avatar with no user associated (status: presence_holiday_present)
    await contains(".o_m2m_avatar").click();
    await waitFor(".o-mail-avatar-card-name:text(Dorothea)")
    await waitFor(".o_employee_presence_status [data-icon='travel'].text-success")

    // 2. Clicking on human resource's avatar with no user associated (status: presence_holiday_absent)
    await contains(".o_m2m_avatar:eq(1)").click();
    await waitFor(".o-mail-avatar-card-name:text(Fernando)")
    await waitFor(".o_employee_presence_status [data-icon='travel'].text-warning")

    // 3. Clicking on human resource's avatar with a user associated
    await contains(".o_m2m_avatar:eq(2)").click();
    await waitFor(".o-mail-avatar-card-name:text(Lucinda)")
    await waitFor(".o-mail-ImStatus[data-icon='travel'].text-success")

    // 4. Clicking on human resource's avatar with a user associated
    await contains(".o_m2m_avatar:eq(3)").click();
    await waitFor(".o-mail-avatar-card-name:text(Cardenio)")
    await waitFor(".o-mail-ImStatus[data-icon='travel'].o-yellow")
});
