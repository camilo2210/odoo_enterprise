import { getService, mockService } from "@web/../tests/web_test_helpers";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { describe, expect, test } from "@odoo/hoot";
import { RecordFileStore } from "@spreadsheet_edition/bundle/image/record_file_store";
import { makeSpreadsheetMockEnv } from "@spreadsheet/../tests/helpers/model";

describe.current.tags("headless");
defineSpreadsheetModels();

test("upload image", async () => {
    const fakeHTTPService = {
        post: (route, params) => {
            expect.step("image uploaded");
            expect(route).toBe("/spreadsheet/res.partner/1/upload_image");
            return JSON.stringify({
                id: 10,
                url: "/web/image/10?access_token=the-image-access-token",
            });
        },
    };
    mockService("http", fakeHTTPService);
    await makeSpreadsheetMockEnv();
    const fileStore = new RecordFileStore("res.partner", 1, getService("http"), getService("orm"));
    const path = await fileStore.upload(
        new File(["image"], "image_name.png", { type: "image/png" })
    );
    expect(path).toBe("/web/image/10?access_token=the-image-access-token");
    expect.verifySteps(["image uploaded"]);
});
