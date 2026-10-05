import { beforeEach, expect, test } from "@odoo/hoot";
import { registry } from "@web/core/registry";
import {
    contains,
    defineModels,
    mountWebClient,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { hrModels } from "@hr/../tests/hr_test_helpers";

defineModels(hrModels);

let checkedIn;
beforeEach(() => {
    checkedIn = false;
    const getEmployeeData = () => ({
        id: serverState.userId,
        name: "Super Employee",
        display_systray: true,
        has_attendance_check_in_ability: true,
        attendance_state: checkedIn ? "checked_in" : "checked_out",
    });
    registry.category("services").add(
        "lazy_session",
        {
            start: () => ({
                getValue: (key, callback) => {
                    const values = {
                        attendance_check_in_ability: true,
                        attendance_state: checkedIn ? "checked_in" : "checked_out",
                        attendance_device_tracking: false,
                        attendance_capture_check_in: false,
                        attendance_break_management: false,
                    };
                    callback(values[key]);
                },
            }),
        },
        { force: true }
    );
    patchWithCleanup(navigator.geolocation, {
        watchPosition() {
            expect.step("watch started");
            return 123;
        },
        clearWatch() {
            expect.step("watch stopped");
        },
    });
    onRpc("/hr_attendance/attendance_user_data", getEmployeeData);
    onRpc("/hr_attendance/systray_check_in_out", () => {
        checkedIn = !checkedIn;
        return getEmployeeData();
    });
});

test("A watch should be started on check in and stopped on check out", async () => {
    onRpc(({ model, method }) => {
        if (method === "update_resource_live_location") {
            expect(model).toBe("res.users");
            expect.step(method);
            return true;
        } else if (method === "should_erase_live_location") {
            expect(model).toBe("res.users");
            expect.step(method);
            return false;
        }
    });
    await mountWebClient();
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='circle']").click();
    await contains("div.o_wrap_btn_sign_out i[data-icon='login']").click();
    expect.verifySteps(["watch started"]);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='circle']").click();
    await contains("div.o_wrap_btn_sign_out i[data-icon='logout']").click();
    expect.verifySteps(["should_erase_live_location", "watch stopped"]);
});

test("The watch should not be resumed if the user was not checked in, even if there was a watch running", async () => {
    await mountWebClient();
    expect.verifySteps([]);
});

test("The watch should be resumed if it was previously running and user was checked in", async () => {
    checkedIn = true;
    await mountWebClient();
    expect.verifySteps(["watch started"]);
});
