import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { assignDialogTestEnv, mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { NextDirectSignDialog } from "@sign/dialogs/dialogs";
import { fakeSignInfoService } from "./dialog_utils";

const mountNextDirectSignDialog = async () => {
    assignDialogTestEnv();
    await mountWithCleanup(NextDirectSignDialog, { props: { close: () => {} } });
};

const documentId = 23;
const signRequestState = "sent";
const tokenList = ["abc", "def"];
const nameList = ["Brandon", "Coleen"];
const requestItemIdList = [11, 12];
const reference = "Contract.pdf";
const lastSignedName = "Adam";

const signInfo = {
    documentId,
    createUid: 7,
    signRequestState,
    tokenList,
    nameList,
    requestItemIdList,
    reference,
    lastSignedName,
    someSignersEmailed: false,
};

mockService("signInfo", fakeSignInfoService(signInfo));

describe.current.tags("desktop");
defineMailModels();

test("next direct sign dialog should render", async () => {
    await mountNextDirectSignDialog();
    expect(".o_nextdirectsign_message").toHaveCount(1, {
        message: "should render next direct sign message",
    });
    expect(".o_nextdirectsign_message p:first-child").toHaveText(
        "The signature of Adam has been saved.",
        { message: "the signer who just signed should be shown" }
    );
    expect(".o_nextdirectsign_message p:last-child").toHaveText(
        "Brandon is next. They can sign now on this device, or later by email.",
        { message: "next signatory should be brandon" }
    );
    expect(".btn-primary").toHaveText("Next signatory (Brandon)");
});

test("next direct sign dialog should go to next document", async () => {
    await mountNextDirectSignDialog();
    mockService("action", {
        doAction(action, params) {
            expect(action.tag).toBe("sign.SignableDocument");
            const expected = {
                id: documentId,
                create_uid: user.userId,
                state: signRequestState,
                token: "abc",
                token_list: ["def"],
                name_list: ["Coleen"],
                request_item_id_list: [12],
                reference,
                some_signers_emailed: false,
            };
            expect(params.additionalContext).toEqual(expected, {
                message: "action should be called with correct params",
            });
        },
    });

    await click(".btn-primary");
});
