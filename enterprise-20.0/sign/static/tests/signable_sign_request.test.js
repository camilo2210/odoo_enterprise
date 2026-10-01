import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { getService, defineModels } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { createDocumentWebClient } from "./action_utils";
import { SignTemplateTag, SignRequest } from "./sign_test_helpers";

const tag = "sign.SignableDocument";

describe.current.tags("desktop");
defineModels([SignRequest, SignTemplateTag]);
defineMailModels();

test("simple rendering", async () => {
    const getDataFromHTML = () => {
        expect.step("getDataFromHTML");
    };
    const config = {
        getDataFromHTML,
        tag,
    };

    await createDocumentWebClient(config);
    await getService("action").doAction(9);
    await animationFrame();
    expect.verifySteps(["getDataFromHTML"]);

    expect(".o_sign_document").toHaveText("def", { message: "should display text from server" });

    expect(".dropdown-toggle .o_sign_refuse_document_button").toHaveCount(0, {
        message: "should show refuse button",
    });
});

test("Show Options and decline during signing", async () => {
    const config = {
        tag,
    };
    await createDocumentWebClient(config);

    await getService("action").doAction(9);
    await animationFrame();

    expect(".o_sign_refuse_document_button").toHaveCount(1, {
        message: "should show Decline to sign",
    });
});
