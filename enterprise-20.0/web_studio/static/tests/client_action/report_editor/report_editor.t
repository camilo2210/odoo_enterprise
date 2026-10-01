import { useEnv } from "@web/owl2/utils";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, queryOne, test } from "@odoo/hoot";
import { hover, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, onPatched, proxy, t, useProps, xml } from "@odoo/owl";
import {
    contains,
    defineModels,
    fields,
    getService,
    mockService,
    models,
    mountWithCleanup,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { ReportEditorModel } from "@web_studio/client_action/report_editor/report_editor_model";
import { defineStudioEnvironment } from "../../studio_tests_context";
import { IrModel } from "@web/../tests/_framework/mock_server/mock_models/ir_model";
import { patch } from "@web/core/utils/patch";
import { location } from "@web/core/browser/browser";
import { setContent } from "@html_editor/../tests/_helpers/selection";

describe.current.tags("desktop");

class ReportPaperFormat extends models.ServerModel {
    _name = "report.paperformat";
}

class IrActionsReport extends models.ServerModel {
    _name = "ir.actions.report";

    paperformat_id = fields.Many2one({ relation: "report.paperformat" });
    display_in_print_menu = fields.Boolean();

    _views = {
        form: `<form><field name="name" /></form>`,
    };

    _records = [
        {
            id: 415,
            report_name: "some_report_name",
            name: "Test report",
        },
    ];
}

patch(IrModel.prototype, {
    studio_model_infos(model_name) {
        const read = this.search([["model", "=", model_name]])[0];
        return {
            ...read,
            record_ids: [1],
        };
    },
});

defineModels([IrActionsReport, ReportPaperFormat]);

async function load_report_editor(request, params) {
    if (request && !params) {
        params = (await request.json()).params;
    }
    return {
        paperformat: {},
        report_data: this.env["ir.actions.report"].browse([params.report_id])[0],
        report_qweb: `<html><body><div id="wrapwrap"><span ws-view-id="205">hello</span></div></body></html>`,
    };
}

onRpc("/web_studio/load_report_editor", load_report_editor);

onRpc("/web_studio/save_report", async function (request) {
    const params = (await request.json()).params;
    if (params.report_changes) {
        this.env["ir.actions.report"].write([params.report_id], params.report_changes);
    }
    return load_report_editor.call(this, null, { report_id: params.report_id });
});

test("setting is in edition doesn't produce intempestive renders", async () => {
    defineMailModels();

    mockService("ui", {
        block: () => expect.step("block"),
        unblock: () => expect.step("unblock"),
    });

    class Child extends Component {
        static template = xml`<div class="child" t-out="this.props.rem.isInEdition"/>`;
        props = useProps({
            rem: t.instanceOf(ReportEditorModel),
        });
        setup() {
            onPatched(() => expect.step("Child rendered"));
        }
    }

    class Parent extends Component {
        static components = { Child };
        static template = xml`
            <Child rem="this.rem" />
            <button class="test-btn" t-on-click="() => this.rem.setInEdition(false)">btn</button>
        `;

        setup() {
            const env = useEnv();
            this.rem = proxy(
                new ReportEditorModel({ services: env.services, resModel: "partner" })
            );
            onPatched(() => expect.step("Parent rendered"));
            this.rem.setInEdition(true);
        }
    }

    await mountWithCleanup(Parent);
    await animationFrame();

    expect.verifySteps(["block"]);
    expect(".child").toHaveText("true");

    await contains("button.test-btn").click();

    expect(".child").toHaveText("false");
    expect.verifySteps(["unblock", "Child rendered"]);
});

test("reports tab disabled when no record", async () => {
    defineStudioEnvironment();
    onRpc("ir.model", "studio_model_infos", ({ args }) => ({
        is_mail_thread: true,
        record_ids: [],
        name: "Custom Partner Model",
        model: args[0],
    }));
    await mountWithCleanup(WebClientEnterprise);
    await contains("a.o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_web_studio_navbar_item:not(.o_disabled)").click();
    expect(".o_web_studio_menu .o_menu_sections button:contains(Reports)").toHaveCount(1);
    expect(".o_web_studio_menu .o_menu_sections button:contains(Reports):disabled").toHaveCount(1);
    await hover(".o_web_studio_menu .o_menu_sections button:contains(Reports)");
    await waitFor(".o-overlay-item", { timeout: 1000 });
    expect(".o-overlay-item").toHaveText(
        "You cannot edit a report while there is no Custom Partner Model (partner)"
    );
});

test("open report form view from cog", async () => {
    defineMailModels();
    serverState.debug = "1";

    onRpc("/web_studio/save_report", async function (request) {
        const params = (await request.json()).params;
        expect.step("save report");
        expect(params.html_parts).toEqual({
            205: [
                {
                    call_group_key: null,
                    call_key: null,
                    html: '<span ws-view-id="205"><p>edited</p></span>',
                    type: "full",
                },
            ],
        });
        return {
            report_qweb: `<html><body><div id="wrapwrap"><span ws-view-id="205">hello modifed</span></div></body></html>`,
        };
    });

    await mountWithCleanup(WebClientEnterprise);
    await waitFor(".o_home_menu");
    await getService("action").doAction({
        name: "Some Action",
        type: "ir.actions.act_window",
        res_model: "res.partner",
        res_id: 1,
        views: [[false, "form"]],
        target: "main",
    });
    await waitFor(".o_form_view");
    await animationFrame();

    location.href = `${location.href}/studio?mode=editor&_tab=reports&_report_id=415`;
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
    await waitFor(".o_studio .o-web-studio-report-editor");
    await waitFor(":iframe .odoo-editor-editable span");
    const editable = queryOne(":iframe .odoo-editor-editable span");
    setContent(editable, "<p>edited</p>");
    await contains(
        ".o-web-studio-report-editor-sidebar button[title='Edit report action']"
    ).click();
    await waitFor(".o_form_view");
    expect.verifySteps(["save report"]);

    expect(".o_web_studio_breadcrumb .breadcrumb-item").toHaveCount(2);
    expect(".o_web_studio_breadcrumb").toHaveText("REPORTS\nTEST REPORT");

    await contains(".breadcrumb-item.active").click();
    await waitFor(".o_studio .o-web-studio-report-editor");
    expect(".o_web_studio_breadcrumb .breadcrumb-item").toHaveCount(2);
    expect(".o_web_studio_breadcrumb").toHaveText("REPORTS\nTEST REPORT");
});
