import {
    click,
    contains,
    insertText,
    scroll,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { expect, describe, runAllTimers, test } from "@odoo/hoot";
import { VOIP_PAGE_SIZE } from "@voip/softphone/softphone_model";
import {
    openRecentContactSearch,
    openSoftphone,
    setupVoipTests,
} from "@voip/../tests/voip_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";
import { onRpc, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Partners with a phone number are displayed in Recent contact search", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "Michel Landline", phone: "+1-307-555-0120" },
        { name: "Patrice Nomo" },
    ]);
    await start();
    await openRecentContactSearch("Michel");
    await contains(".o-voip-TabEntry", { count: 1 });
    await contains(".o-voip-TabEntry span", { text: "Michel Landline" });
    await contains(".o-voip-TabEntry span", { text: "Patrice Nomo", count: 0 });
});

test("Typing in the search bar should search by complete name and displays the matching contacts' name", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "Morshu RTX", complete_name: "Hoolopee, Morshu RTX", phone: "+61-855-527-77" },
        { name: "Gargamel", complete_name: "Gargamel", phone: "+61-855-583-671" },
    ]);
    await start();
    await openRecentContactSearch("Hoolopee");
    await contains(".o-voip-TabEntry span", { text: "Morshu RTX" });
    await contains(".o-voip-TabEntry .o-voip-highlighted-letter", { text: "Hoolopee" });
    await contains(".o-voip-TabEntry span", { text: "Gargamel", count: 0 });

    await insertText("#o-voip-Tab-searchInput", "Morshu", { replace: true });
    await contains(".o-voip-TabEntry .o-voip-highlighted-letter", {
        text: "Morshu",
        count: 1,
    });
});

test("Contact search matches phone_formatted", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "John Doe",
        phone: "1234567890",
        phone_sanitized: "+11234567890",
        phone_formatted: "+1 123 456 7890",
    });
    await start();
    // Search term carries a country-code prefix that does not match the raw
    // `phone`, but should match `phone_formatted` via fallback.
    await openRecentContactSearch("+11234567890");
    await contains(".o-voip-TabEntry span", { text: "John Doe" });
    await contains(".o-voip-TabEntry .o-voip-highlighted-letter", { text: "+1 123 456 7890" });
});

test("Scrolling to bottom loads more contacts", async () => {
    const pyEnv = await startServer();
    let rpcCount = 0;
    onRpc("res.partner", "get_contacts", () => {
        ++rpcCount;
    });
    await start();
    for (let i = 0; i < 10; ++i) {
        // zero-pad so the names sort in creation order under complete_name (res.partner._order),
        // keeping the offset pagination stable when the next batch is added below.
        pyEnv["res.partner"].create({
            name: `Contact ${String(i).padStart(2, "0")}`,
            phone: `09225 982 ext. ${i}`,
        });
    }
    await openRecentContactSearch("Contact");
    await contains(".o-voip-TabEntry", { count: 10 });
    expect(rpcCount).toBe(1);
    for (let i = 0; i < 10; ++i) {
        pyEnv["res.partner"].create({ name: `Contact ${i + 10}`, phone: `040 2805 ext. ${i}` });
    }
    await contains(".o-voip-TabEntry", { count: 10 });
    await scroll(".o-voip-AddressBook div.overflow-auto", "bottom");
    await contains(".o-voip-TabEntry", { count: 20 });
    expect(rpcCount).toBe(2);
});

test("Contacts are sorted without section titles", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "", phone: "+1-555-0001" }, // Contact with empty name
        { name: false, phone: "+1-555-0002" }, // Contact with false name
        { name: "Alice", phone: "+1-555-0003" }, // Normal contact
    ]);
    await start();
    await openRecentContactSearch("555");
    await contains(".o-voip-TabEntry", { count: 3 });
    await contains(".o-voip-AddressBook h2", { count: 0 });
    const contacts = Array.from(
        document.querySelectorAll(".o-voip-AddressBook .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(contacts).toEqual(["Alice", "+1-555-0002", "+1-555-0001"]);
});

test("Contact search highlights matching visible fields", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        email: "alice@example.com",
        function: "Alice Engineer",
        name: "Alice Highlight",
        phone: "+1-555-0004",
    });

    await start();
    await openRecentContactSearch("Alice");
    await contains(".o-voip-AddressBook .o-voip-TabEntry:contains('Alice Highlight')", {
        contains: [[".o-voip-highlighted-letter", { text: "Alice" }]],
    });
    await contains(
        ".o-voip-AddressBook .o-voip-TabEntry:contains('Alice Highlight') [data-icon='business']"
    );
    await contains(
        ".o-voip-AddressBook .o-voip-TabEntry:contains('Alice Highlight') [data-icon='business'] + span",
        {
            text: "Alice Engineer",
            contains: [[".o-voip-highlighted-letter", { count: 0 }]],
        }
    );
    await insertText("#o-voip-Tab-searchInput", "555", { replace: true });
    await contains(".o-voip-AddressBook .o-voip-TabEntry:contains('Alice Highlight')", {
        contains: [[".o-voip-highlighted-letter", { text: "555" }]],
    });
    await contains(
        ".o-voip-AddressBook .o-voip-TabEntry:contains('Alice Highlight') [data-icon='business']",
        {
            count: 0,
        }
    );
    await insertText("#o-voip-Tab-searchInput", "example", { replace: true });
    await contains(".o-voip-AddressBook .o-voip-TabEntry:contains('Alice Highlight')", {
        text: "alice@example.com",
        contains: [[".o-voip-highlighted-letter", { text: "example" }]],
    });
});

test("Contact search supports T9 matches", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1-555-0005", t9_name: " 5646 363" },
        { name: "Bob Wilson", phone: "+1-555-0006", t9_name: " 262 94576" },
    ]);

    await start();
    await openRecentContactSearch("5646");
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "John Doe" });
    await contains(".o-voip-AddressBook .o-voip-TabEntry:contains('John Doe')", {
        contains: [[".o-voip-highlighted-letter", { text: "John" }]],
    });
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", {
        text: "Bob Wilson",
        count: 0,
    });
});

test("Contact search sorts recently-called contacts first", async () => {
    const pyEnv = await startServer();
    const getContactsRpcOffsets = [];
    onRpc("res.partner", "get_contacts", (args) => {
        if (args.kwargs.search_terms === "Ranked") {
            getContactsRpcOffsets.push(args.kwargs.offset);
            expect(args.kwargs.prioritized_contacts_limit).toBe(3);
        }
    });
    for (let i = 0; i < VOIP_PAGE_SIZE; ++i) {
        pyEnv["res.partner"].create({
            name: `Ranked Before ${String(i).padStart(2, "0")}`,
            phone: `+1-555-20${String(i).padStart(2, "0")}`,
        });
    }
    const frequentPartnerId = pyEnv["res.partner"].create({
        name: "Ranked Frequent",
        phone: "+1-555-1001",
    });
    const recentPartnerId = pyEnv["res.partner"].create({
        name: "Ranked Recent",
        phone: "+1-555-1002",
    });
    const oldPartnerId = pyEnv["res.partner"].create({
        name: "Ranked Old",
        phone: "+1-555-1003",
    });
    const now = luxon.DateTime.now();

    await start();
    await openSoftphone();
    await click("button[data-tab='recent']");
    await contains("button[data-tab='recent'].active");

    pyEnv["voip.call"].create([
        {
            phone_number: "+1-555-1001",
            partner_id: frequentPartnerId,
            user_id: serverState.userId,
            create_date: serializeDateTime(now.minus({ days: 3 })),
        },
        {
            phone_number: "+1-555-1001",
            partner_id: frequentPartnerId,
            user_id: serverState.userId,
            create_date: serializeDateTime(now.minus({ days: 2 })),
        },
        {
            phone_number: "+1-555-1002",
            partner_id: recentPartnerId,
            user_id: serverState.userId,
            direction: "incoming",
            create_date: serializeDateTime(now.minus({ days: 1 })),
        },
        {
            phone_number: "+1-555-1003",
            partner_id: oldPartnerId,
            user_id: serverState.userId,
            create_date: serializeDateTime(now.minus({ months: 2 })),
        },
    ]);

    await insertText("input[id='o-voip-Tab-searchInput']", "Ranked");
    await contains(".o-voip-AddressBook");
    await runAllTimers();
    await contains(".o-voip-AddressBook h2", { count: 0 });
    const contactTitles = Array.from(
        document.querySelectorAll(".o-voip-AddressBook .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(contactTitles.slice(0, 3)).toEqual(["Ranked Recent", "Ranked Frequent", "Ranked Old"]);
    expect(contactTitles.length).toBe(VOIP_PAGE_SIZE);
    expect(getContactsRpcOffsets).toEqual([0]);

    await scroll(".o-voip-AddressBook div.overflow-auto", "bottom");
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "Ranked Before 12" });
    const loadedContactTitles = Array.from(
        document.querySelectorAll(".o-voip-AddressBook .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(loadedContactTitles.length).toBe(VOIP_PAGE_SIZE + 3);
    expect(getContactsRpcOffsets).toEqual([0, VOIP_PAGE_SIZE]);
});

test("In German, umlauts are expanded to their two-letter equivalents before sorting", async () => {
    serverState.lang = "de_DE";
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "Göbel", phone: "+1-555-0001" },
        { name: "Godbolt", phone: "+1-555-0002" },
        { name: "Goethe", phone: "+1-555-0003" },
        { name: "Müller", phone: "+1-555-0004" },
        { name: "Mueller", phone: "+1-555-0005" },
        { name: "Muhammad", phone: "+1-555-0006" },
    ]);
    await start();
    await openRecentContactSearch("555");
    await contains(".o-voip-TabEntry-title:text(Goethe)");
    const contacts = Array.from(document.querySelectorAll(".o-voip-TabEntry-title"), (node) =>
        node.textContent.trim()
    );
    const expectedOrder = ["Godbolt", "Göbel", "Goethe", "Mueller", "Müller", "Muhammad"];
    expect(contacts).toEqual(expectedOrder);
});

test("Numbers in contact names are sorted by value", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "Guest 10", phone: "+1-555-0001" },
        { name: "Guest 0", phone: "+1-555-0002" },
        { name: "Guest 9", phone: "+1-555-0003" },
        { name: "Guest 1", phone: "+1-555-0004" },
        { name: "Guest 01", phone: "+1-555-0005" },
    ]);
    await start();
    await openRecentContactSearch("555");
    await contains(".o-voip-TabEntry-title:text(Guest 1)");
    const contacts = Array.from(document.querySelectorAll(".o-voip-TabEntry-title"), (node) =>
        node.textContent.trim()
    );
    const expectedOrder = ["Guest 0", "Guest 01", "Guest 1", "Guest 9", "Guest 10"];
    expect(contacts).toEqual(expectedOrder);
});
