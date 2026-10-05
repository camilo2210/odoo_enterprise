import { expect, test } from "@odoo/hoot";
import { animationFrame, click, queryFirst, queryOne, waitFor, waitForNone } from "@odoo/hoot-dom";
import { defineModels } from "@web/../tests/web_test_helpers";

import {
    DocumentsModels,
    getDocumentsTestServerModelsData,
    makeDocumentRecordData,
} from "./helpers/data";
import { makeDocumentsMockEnv } from "./helpers/model";
import { mountDocumentsKanbanView } from "./helpers/views/kanban";

defineModels(DocumentsModels);

function dragOver(el) {
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(new File(["content"], "test.txt", { type: "text/plain" }));
    el.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer }));
}

function dragLeave(el) {
    el.dispatchEvent(new DragEvent("dragleave", { bubbles: true, cancelable: true }));
}

async function selectFolder(valueId) {
    const selector = `.o_search_panel_category_value[data-value-id='${valueId}']`;
    if (!queryFirst(selector)) {
        // Folders hang under the `Company` root, which is folded on mount.
        await click(".o_search_panel_category_value[data-value-id='COMPANY'] .o_toggle_fold");
        await animationFrame();
    }

    await click(`${selector} .o_search_panel_label_btn`);
    await animationFrame();
    await waitFor(`${selector} .o_search_panel_category_value_header.active`);
}

test.tags("desktop");
test("DocumentsDropZone: drop is authorized in a writable folder, refused in a read-only one", async () => {
    const serverData = getDocumentsTestServerModelsData([
        // `Folder 1` (id 1, `edit` permission) comes with the default data set.
        makeDocumentRecordData(2, "Folder 2", { type: "folder", user_permission: "view" }),
        makeDocumentRecordData(3, "Doc 1", { folder_id: 1 }),
        makeDocumentRecordData(4, "Doc 2", { folder_id: 2 }),
    ]);
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    expect(".o_documents_upload_text").toHaveCount(0);
    expect(".o_kanban_renderer").not.toHaveClass("o_documents_drop_over");
    expect(".o_kanban_renderer").not.toHaveClass("o_documents_drop_over_unauthorized");

    // `Folder 1` grants `edit`, so uploading into it is allowed.
    await selectFolder(1);
    dragOver(queryOne(".o_kanban_renderer"));
    await waitFor(".o_documents_drop_over_zone");
    expect(".o_kanban_renderer").toHaveClass("o_documents_drop_over");
    expect(".o_kanban_renderer").not.toHaveClass("o_documents_drop_over_unauthorized");
    expect(".o_documents_upload_text.text-white").toHaveCount(1);
    expect(".o_documents_upload_text.text-danger").toHaveCount(0);

    dragLeave(queryOne(".o_kanban_renderer"));
    await waitForNone(".o_documents_upload_text");
    expect(".o_kanban_renderer").not.toHaveClass("o_documents_drop_over");

    // `Folder 2` grants `view` only: the same drag must show the _unauthorized overlay.
    await selectFolder(2);
    dragOver(queryOne(".o_kanban_renderer"));
    await waitFor(".o_documents_drop_over_unauthorized_zone");
    expect(".o_kanban_renderer").toHaveClass("o_documents_drop_over_unauthorized");
    expect(".o_kanban_renderer").not.toHaveClass("o_documents_drop_over");
    expect(".o_documents_upload_text.text-danger").toHaveCount(1);
    expect(".o_documents_upload_text.text-white").toHaveCount(0);

    dragLeave(queryOne(".o_kanban_renderer"));
    await waitForNone(".o_documents_upload_text");
    expect(".o_kanban_renderer").not.toHaveClass("o_documents_drop_over_unauthorized");
});

test("DocumentsDropZone: overlay tracks the renderer's scrollTop", async () => {
    const serverData = getDocumentsTestServerModelsData(
        Array.from({ length: 12 }, (_, i) =>
            makeDocumentRecordData(i + 2, `Doc ${i + 1}`, { folder_id: 1 })
        )
    );
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    const renderer = queryOne(".o_kanban_renderer");
    // Make the renderer scrollable so scrollTop actually moves in HOOT's real browser.
    renderer.style.maxHeight = "200px";
    renderer.style.overflowY = "scroll";
    renderer.scrollTop = 150;

    expect(renderer.scrollTop).toBeGreaterThan(0);
    const scrollTop = renderer.scrollTop;
    renderer.dispatchEvent(new Event("scroll", { bubbles: true }));
    await animationFrame();

    dragOver(renderer);
    await animationFrame();

    const overlay = await waitFor(".o_documents_upload_text");
    const zone = overlay.closest("[style*='top']");
    expect(zone.style.top).toBe(`${scrollTop}px`);

    // Scrolling again while the overlay is visible keeps it aligned (live path).
    renderer.scrollTop = scrollTop + 40;
    const newScrollTop = renderer.scrollTop;
    renderer.dispatchEvent(new Event("scroll", { bubbles: true }));
    await animationFrame();

    expect(zone.style.top).toBe(`${newScrollTop}px`);
});
