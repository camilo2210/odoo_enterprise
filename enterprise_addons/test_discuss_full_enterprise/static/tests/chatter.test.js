import { mailChatterMessageActionsInvisibleWhenNotHovered } from "@mail/../tests/mail_shared_tests";

import { defineTestDiscussFullEnterpriseModels } from "@test_discuss_full_enterprise/../tests/test_discuss_full_enterprise_test_helpers";

import { describe, test } from "@odoo/hoot";

describe.current.tags("desktop");
defineTestDiscussFullEnterpriseModels();

test(
    "Chatter message actions should be invisible when not mouse-hovered (including ai)",
    mailChatterMessageActionsInvisibleWhenNotHovered
);
