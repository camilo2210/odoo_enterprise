import { describe, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { contains, defineModels, onRpc } from "@web/../tests/web_test_helpers";
import { DocumentsModels, getDocumentsTestServerModelsData, makeDocumentRecordData } from "@documents/../tests/helpers/data";
import { makeDocumentsMockEnv } from "@documents/../tests/helpers/model";
import { basicDocumentsKanbanArch, mountDocumentsKanbanView } from "@documents/../tests/helpers/views/kanban";

describe.current.tags("desktop");

defineModels({
    ...DocumentsModels,
});

onRpc("/documents/touch/<access_token>", () => ({}));

const DocumentsAccountKanbanArch = basicDocumentsKanbanArch.replace(
    `<field name="id"/>`,
    `<field name="id"/><field name="has_embedded_pdf"/>`
);

test("Document preview for xml with embedded_pdf", async function () {
    const serverData = getDocumentsTestServerModelsData([
        makeDocumentRecordData(2, "simple_file.xml", {
            folder_id: 1,
            attachment_id: 1,
            mimetype: "text/plain",
            has_embedded_pdf: true,
        }),
    ]);
    serverData["ir.attachment"] = [
        { id: 1, name: "simple_file.xml", mimetype: "text/plain" },
    ];

    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView({ arch: DocumentsAccountKanbanArch });

    await contains(".o_kanban_record:contains('simple_file.xml') div[name='document_preview']").click();
    await waitFor("iframe.o-FileViewer-view", { count: 1 });
});
