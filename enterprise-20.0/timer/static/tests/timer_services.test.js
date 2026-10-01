import { expect, test } from "@odoo/hoot";
import { getMockEnv, makeTestApp } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { TimerReactive } from "@timer/models/timer_reactive";

const { DateTime } = luxon;

defineMailModels();

test("timer_reactive handle displaying start time", async () => {
    await makeTestApp();
    const timerReactive = new TimerReactive(getMockEnv());
    timerReactive.formatTime();
    expect(timerReactive.time).toBe("00:00:00");

    const timerStart = DateTime.now().minus({ seconds: 1 });
    timerReactive.setTimer(0, timerStart);
    timerReactive.formatTime();
    expect(timerReactive.time).toBe("00:00:01");
});

test("timer_reactive handle displaying durations longer than 24h", async () => {
    await makeTestApp();
    const timerReactive = new TimerReactive(getMockEnv());
    const timerStart = DateTime.now().minus({ days: 2 });
    timerReactive.setTimer(0, timerStart);
    timerReactive.formatTime();
    expect(timerReactive.time).toBe("48:00:00");
});
