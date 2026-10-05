/** @odoo-module **/

import { beforeEach, expect, test } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";

import mobile from "@web_mobile/js/services/core";
import { downloadFile } from "@web/core/network/download";

beforeEach(() => {
    patchWithCleanup(mobile.methods, {
        downloadFile: (payload) => expect.step(payload),
    });
    patchWithCleanup(browser.console, {
        warn: (message) => expect.step(message),
    });
});

test("downloadFile: the host is removed from an absolute URL before calling mobile.methods.downloadFile", async () => {
    await downloadFile("https://www.hoot.test/web/content/123?download=true");
    expect.verifySteps([{ form: { method: "GET" }, url: "/web/content/123?download=true" }]);
});

test("downloadFile: a relative URL is forwarded as-is to mobile.methods.downloadFile", async () => {
    await downloadFile("/web/content/123?download=true");
    expect.verifySteps([{ form: { method: "GET" }, url: "/web/content/123?download=true" }]);
});

test("downloadFile: Blob content is not handled, logs a warning instead", async () => {
    const blob = new Blob(["hello world"], { type: "text/plain" });
    await downloadFile(blob, "test.txt");
    expect.verifySteps([
        "downloadFile: the native saveFile bridge only supports URL downloads; ignoring Blob/string content.",
    ]);
});

test("downloadFile: string content with filename/mimetype is not handled, logs a warning instead", async () => {
    await downloadFile('{"foo":"bar"}', "export.json", "application/json");
    expect.verifySteps([
        "downloadFile: the native saveFile bridge only supports URL downloads; ignoring Blob/string content.",
    ]);
});
