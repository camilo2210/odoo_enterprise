import { test, expect } from "@odoo/hoot";
import { PlanningSlotSelectionPopup } from "@pos_sale_planning/app/components/planning_slot_selection_popup/planning_slot_selection_popup";

const makeSlot = (id, resourceName, slotDisplayName) => ({
    id,
    display_name: slotDisplayName,
    resource_ids: [{ name: resourceName }],
});

const makeComp = (query, slots) => {
    const comp = Object.create(PlanningSlotSelectionPopup.prototype);
    comp.state = { query, slotsToDisplay: slots };
    return comp;
};

test("slotsToDisplay - empty query returns all slots unchanged", () => {
    const slots = [makeSlot(1, "Room A", "Slot for John"), makeSlot(2, "Desk B", "Slot for Jane")];
    const comp = makeComp("", slots);
    expect(comp.slotsToDisplay).toEqual(slots);
});

test("slotsToDisplay - name matches take priority over slot matches", () => {
    const slots = [
        makeSlot(1, "conference room", "Slot 1"),
        makeSlot(2, "Meeting Room", "conference slot 2"),
    ];
    const comp = makeComp("conference", slots);

    const result = comp.slotsToDisplay;
    expect(result[0].id).toBe(1);
    expect(result[1].id).toBe(2);
});

test("slotsToDisplay - name matches sorted by name length (shortest first)", () => {
    const slots = [
        makeSlot(1, "a longer room name", "Slot 1"),
        makeSlot(2, "room", "Slot 2"),
        makeSlot(3, "room b", "Slot 3"),
    ];
    const comp = makeComp("room", slots);

    const result = comp.slotsToDisplay;
    expect(result.map((r) => r.id)).toEqual([2, 3, 1]);
});

test("slotsToDisplay - slot matches sorted by slot display_name length (shortest first)", () => {
    const slots = [
        makeSlot(1, "Desk A", "very long slot name here"),
        makeSlot(2, "Desk B", "short slot"),
        makeSlot(3, "Desk C", "medium slot xx"),
    ];
    const comp = makeComp("slot", slots);

    const result = comp.slotsToDisplay;
    expect(result.map((r) => r.id)).toEqual([2, 3, 1]);
});

test("slotsToDisplay - matching is case-insensitive", () => {
    const slots = [makeSlot(1, "Meeting Room", "Conference Slot")];
    const comp = makeComp("MEETING", slots);

    expect(comp.slotsToDisplay).toHaveLength(1);
    expect(comp.slotsToDisplay[0].id).toBe(1);
});

test("slotsToDisplay - returns empty array when nothing matches", () => {
    const slots = [makeSlot(1, "Meeting Room", "Slot for John")];
    const comp = makeComp("xyz_no_match_999", slots);

    expect(comp.slotsToDisplay).toHaveLength(0);
});

test("slotsToDisplay - resource matching by name is not duplicated in slot matches", () => {
    // resource name matches AND slot name also contains the term — must appear only once
    const slots = [makeSlot(1, "room", "room slot")];
    const comp = makeComp("room", slots);

    const result = comp.slotsToDisplay;
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
});

test("slotsToDisplay - name matches and slot matches are concatenated correctly", () => {
    const slots = [
        makeSlot(1, "Desk", "Slot 1"),
        makeSlot(2, "Room", "desk slot 2"),
        makeSlot(3, "Cabin", "Slot 3"),
    ];
    const comp = makeComp("desk", slots);

    const result = comp.slotsToDisplay;
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe(1); // name match
    expect(result[1].id).toBe(2); // slot match
});
