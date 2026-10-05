import {
    click,
    contains,
    defineMailModels,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { getMockEnv, patchWithCleanup } from "@web/../tests/web_test_helpers";

import { user } from "@web/core/user";

describe.current.tags("desktop");
defineMailModels();

test("system users are offered to install Odoo Phone from a call activity", async () => {
    patchWithCleanup(user, { isSystem: true });
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    pyEnv["mail.activity"].create({
        phone: "+1 202 555 0182",
        res_id: partnerId,
        res_model: "res.partner",
    });
    await start();
    patchWithCleanup(getMockEnv().services, { voip: undefined });
    await openFormView("res.partner", partnerId);

    await click(".o-mail-Activity-call");

    await contains(".o_phone_install_dialog");
});
