import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, setInputFiles } from "@odoo/hoot-dom";
import { contains, defineModels, mockService } from "@web/../tests/web_test_helpers";
import { EventBus } from "@odoo/owl";

import { DocumentsModels, getDocumentsTestServerModelsData } from "./helpers/data";
import { makeDocumentsMockEnv } from "./helpers/model";
import { mountDocumentsKanbanView } from "./helpers/views/kanban";

describe.current.tags("mobile");

defineModels(DocumentsModels);

test("Upload from control panel in mobile mode", async () => {
    const _bus = new EventBus();
    mockService("file_upload", {
        bus: _bus,
        upload: (route) => {
            if (route.startsWith("/documents/upload")) {
                _bus.trigger("FILE_UPLOAD_LOADED", {
                    upload: {
                        data: new FormData(),
                        xhr: { status: 200, response: '{ "records": [] }' },
                    },
                });
                expect.step("doc uploaded");
            }
        },
    });

    const serverData = getDocumentsTestServerModelsData();
    await makeDocumentsMockEnv({ serverData });
    await mountDocumentsKanbanView();

    await contains("button.o-control-panel-adaptive-dropdown").click();
    await contains(".btn-primary.o-dropdown-caret.o-dropdown--has-parent").click();
    await contains(".o-dropdown-item.o_documents_kanban_upload").click();
    await animationFrame();

    await setInputFiles([new File(["fake_file"], "fake_file.txt", { type: "text/plain" })]);
    await animationFrame();

    expect.verifySteps(["doc uploaded"]);
});
