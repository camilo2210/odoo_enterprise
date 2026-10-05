import { KnowledgeArticleItemsCommonRenderer } from "@knowledge/views/item_calendar/item_calendar_view";
import { defineKnowledgeModels } from "@knowledge/../tests/knowledge_test_helpers";

import { beforeEach, expect, test } from "@odoo/hoot";
import { queryFirst, waitFor, waitForNone } from "@odoo/hoot-dom";
import { mountWithCleanup, preloadBundle } from "@web/../tests/web_test_helpers";
import {
    DEFAULT_DATE,
    FAKE_MODEL,
} from "@web/../tests/views/calendar/calendar_test_helpers";
import { CallbackRecorder } from "@web/search/action_hook";
import { Component, xml, proxy } from "@odoo/owl";

defineKnowledgeModels();

const WEEK_MODEL = { ...FAKE_MODEL, scale: "week" };

const BASE_PROPS = {
    model: WEEK_MODEL,
    initialDate: DEFAULT_DATE,
    createRecord() {},
    deleteRecord() {},
    editRecord() {},
    callbackRecorder: new CallbackRecorder(),
    onSquareSelection() {},
    cleanSquareSelection() {},
};

class RendererWrapper extends Component {
    static components = { KnowledgeArticleItemsCommonRenderer };
    static template = xml`<KnowledgeArticleItemsCommonRenderer t-props="this.childProps"/>`;
    setup() {
        this.childProps = proxy({ ...BASE_PROPS, slotMinTime: "00:00", slotMaxTime: "24:00" });
    }
}

preloadBundle("web.fullcalendar_lib");
beforeEach(() => {
    luxon.Settings.defaultZone = "UTC+1";
});

test("slotMinTime and slotMaxTime are applied to FullCalendar when props change", async () => {
    const wrapper = await mountWithCleanup(RendererWrapper);

    // With slotMinTime="00:00", the 00:00 & 23:00 time slot should be present (2 els: label + lane)
    await waitFor(`.fc-timegrid-slot[data-time="00:00:00"]`);
    expect(`.fc-timegrid-slot[data-time="00:00:00"]`).toHaveCount(2);
    expect(`.fc-timegrid-slot[data-time="23:00:00"]`).toHaveCount(2);

    // Change slotMinTime to 10:00 — the effect must call fc.api.setOption to update FC.
    // FullCalendar hides slots before slotMinTime, so the 00:00 slot disappears...
    wrapper.childProps.slotMinTime = "10:00";
    await waitForNone(`.fc-timegrid-slot[data-time="00:00:00"]`);
    // ...and the 10:00 slot becomes the first visible slot
    const firstSlot = queryFirst(".fc-timegrid-slot[data-time]");
    expect(firstSlot.dataset.time).toBe("10:00:00");

    // Change slotMaxTime to 14:00 — the 23:00 slot (after slotMaxTime) disappears
    wrapper.childProps.slotMaxTime = "14:00";
    await waitForNone(`.fc-timegrid-slot[data-time="23:00:00"]`);

    // Should be able to reset
    wrapper.childProps.slotMinTime = "00:00";
    await waitFor(`.fc-timegrid-slot[data-time="00:00:00"]`);
    expect(`.fc-timegrid-slot[data-time="00:00:00"]`).toHaveCount(2);
});
