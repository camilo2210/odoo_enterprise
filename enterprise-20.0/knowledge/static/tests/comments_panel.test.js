import { KnowledgeCommentsPanel } from "@knowledge/comments/comments_panel/comments_panel";
import { PanelState } from "@knowledge/components/side_panel/panel_state";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { Component, t, useProps, xml } from "@odoo/owl";
import { expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    assignTestEnv,
    getService,
    makeTestApp,
    mockService,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

defineMailModels();

test("switching mode reloads and re-renders the matching threads", async () => {
    // Stub the (heavy) thread component with a light marker showing its threadId.
    class ThreadStub extends Component {
        static template = xml`<div class="test-thread" t-out="this.props.threadId"/>`;
        props = useProps({
            threadId: t.any(),
        });
    }
    patchWithCleanup(KnowledgeCommentsPanel, {
        components: { KnowledgeCommentsThread: ThreadStub },
    });
    const loadDomains = [];
    mockService("knowledge.comments", {
        loadRecords(_resId, { domain }) {
            loadDomains.push(domain);
            return Promise.resolve(0);
        },
    });

    const panelState = new PanelState();
    assignTestEnv({ panelState, model: { root: { resId: 1 } } });

    await makeTestApp();
    panelState.commentsState = getService("knowledge.comments").getCommentsState();
    Object.assign(panelState.commentsState.threadRecords, {
        10: { is_resolved: false, write_date: "2024-01-02 00:00:00" },
        20: { is_resolved: true, write_date: "2024-01-01 00:00:00" },
    });
    panelState.setActivePanel("comments");

    await mountWithCleanup(KnowledgeCommentsPanel);
    await animationFrame();

    // Default "unresolved" mode
    expect(loadDomains.at(-1)).toEqual([["is_resolved", "=", false]], {
        message: "initial load uses the unresolved domain",
    });
    expect(".test-thread").toHaveCount(1);
    expect(".test-thread").toHaveText("10");
    expect(".o_comments_helper").toHaveCount(0);

    await click("button[name=resolved]");
    await animationFrame();

    expect(loadDomains.at(-1)).toEqual([["is_resolved", "=", true]], {
        message: "switching to resolved mode reloads with the resolved domain",
    });
    expect(".test-thread").toHaveCount(1);
    expect(".test-thread").toHaveText("20");
});
