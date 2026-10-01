import {
    click,
    contains,
    editInput,
    focus,
    mailModels,
    openFormView,
    patchUiSize,
    SIZES,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { beforeEach, expect, test } from "@odoo/hoot";
import { animationFrame, queryFirst, manuallyDispatchProgrammaticEvent, waitFor, waitForNone } from "@odoo/hoot-dom";
import { defineModels, onRpc } from "@web/../tests/web_test_helpers";
import {
    getBoxesData,
} from "./helpers";
import { ExtractMixinWithWordsModel, ManualCorrectionModel, ManualCorrectionLineModel } from "./mock_server/mock_models/manual_correction_model.js";

beforeEach(() => {
    patchUiSize({ size: SIZES.XXL });
});

defineModels({ ...mailModels, ExtractMixinWithWordsModel, ManualCorrectionModel, ManualCorrectionLineModel });

const IMAGE_WIDTH = 210;
const IMAGE_HEIGHT = 297;

const boxes = getBoxesData();
const allBoxes = [];
for (const boxesForType of Object.values(boxes)) {
    for (const pageBoxes of Object.values(boxesForType)) {
        allBoxes.push(...pageBoxes);
    }
}

async function focusField(selector) {
    await focus(selector);
    await waitFor(".o_extract_mixin_box", { timeout: 2000 });
}

async function unfocusField(selector) {
    queryFirst(selector).blur();
    await contains(".o_extract_mixin_box", { count: 0 });
}

async function clickOnBox(value) {
    const matchingBox = allBoxes.find((box) => box.text === value);
    await click(queryFirst(`.o_extract_mixin_box[data-id="${matchingBox.id}"]`));
}

function rectangularSelection(startPos, endPos) {
    const boxLayer = queryFirst(".o_extract_mixin_box_layer");
    const boxLayerViewportOffset = boxLayer.getBoundingClientRect();
    manuallyDispatchProgrammaticEvent(boxLayer, "mousedown", {
        clientX: boxLayerViewportOffset.left + Math.round(startPos.x * IMAGE_WIDTH),
        clientY: boxLayerViewportOffset.top + Math.round(startPos.y * IMAGE_HEIGHT),
    });
    manuallyDispatchProgrammaticEvent(boxLayer, "mousemove", {
        clientX: boxLayerViewportOffset.left + Math.round(endPos.x * IMAGE_WIDTH),
        clientY: boxLayerViewportOffset.top + Math.round(endPos.y * IMAGE_HEIGHT),
    });
    manuallyDispatchProgrammaticEvent(boxLayer, "mouseup");
}

test("basic", async () => {
    const pyEnv = await startServer();
    const recordId = pyEnv["iap_extract.manual.correction"].create({
        extract_state: "waiting_validation",
    });
    const irAttachmentId = pyEnv["ir.attachment"].create({
        name: "test_image.png",
        res_model: "iap_extract.manual.correction",
        res_id: recordId,
        mimetype: "image/png",
    });
    pyEnv["iap_extract.manual.correction"].write([recordId], {
        extract_attachment_id: irAttachmentId,
    });
    pyEnv["mail.message"].create({
        attachment_ids: [irAttachmentId],
        model: "iap_extract.manual.correction",
        res_id: recordId,
    });
    pyEnv["res.partner"].create({ name: "Hello world partner" });

    onRpc("iap_extract.manual.correction", "get_boxes", () => {
        return boxes;
    });
    onRpc("iap_extract.manual.correction", "get_currency_from_text", ({ args }) => {
        expect.step("get_currency_from_text");
        const currency = pyEnv["res.currency"].search([['name', '=', args[1]]]);
        if (currency.length === 1) {
            return currency[0];
        }
    });

    await start();
    await openFormView("iap_extract.manual.correction", recordId, {
        arch: `
        <form js_class="manual_correction_form">
            <sheet>
                <group>
                    <field name="extract_state"/>
                    <field name="extract_attachment_id"/>
                    <field name="char_field"/>
                    <field name="text_field"/>
                    <field name="html_field"/>
                    <field name="integer_field"/>
                    <field name="float_field"/>
                    <field name="monetary_field"/>
                    <field name="date_field"/>
                    <field name="datetime_field"/>
                    <field name="currency_id"/>
                    <field name="partner_id"/>
                </group>
                <field name="line_ids">
                    <list editable="bottom">
                        <field name="char_field"/>
                        <field name="date_field"/>
                        <field name="daterange_field_start" string="Date Range" widget="daterange" options="{'end_date_field': 'daterange_field_end', 'always_range': True}"/>
                        <field name="float_field"/>
                    </list>
                </field>
            </sheet>
            <div class="o_attachment_preview"/>
            <chatter/>
        </form>`,
    });
    await contains(".o-mail-Attachment-imgContainer");

    // **** Char field ****
    const charFieldSelector = ".o_field_widget[name=char_field] input";
    await focusField(charFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["word"][0].length });

    await clickOnBox("Hello");
    await contains(charFieldSelector, { value: "Hello" });

    await focusField(charFieldSelector);
    rectangularSelection({ x: 0.15, y: 0.05 }, { x: 0.45, y: 0.15 });  // Select boxes "Hello" and "world"
    await contains(charFieldSelector, { value: "Hello world" });

    await unfocusField(charFieldSelector);

    // **** Text field ****
    const textFieldSelector = ".o_field_widget[name=text_field] textarea";
    await focusField(textFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["word"][0].length });

    await clickOnBox("Hello");
    await contains(textFieldSelector, { value: "Hello" });

    await focusField(textFieldSelector);
    rectangularSelection({ x: 0.15, y: 0.05 }, { x: 0.45, y: 0.15 });  // Select boxes "Hello" and "world"
    await contains(textFieldSelector, { value: "Hello world" });

    await unfocusField(textFieldSelector);

    // **** Html field ****
    const htmlFieldSelector = ".o_field_widget[name=html_field] .odoo-editor-editable";
    await focusField(htmlFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["word"][0].length });

    await clickOnBox("Hello");
    await contains(".o_field_widget[name=html_field] .o-paragraph", { textContent: "Hello" });

    await focusField(htmlFieldSelector);
    rectangularSelection({ x: 0.15, y: 0.05 }, { x: 0.45, y: 0.15 });  // Select boxes "Hello" and "world"
    await contains(".o_field_widget[name=html_field] .o-paragraph", { textContent: "Hello world" });

    await unfocusField(".o_field_widget[name=html_field] .o-paragraph");

    // **** Float field ****
    const floatFieldSelector = ".o_field_widget[name=float_field] input";
    await focusField(floatFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["number"][0].length });

    await clickOnBox(123.45);
    await contains(floatFieldSelector, { value: "123.45" });

    await focusField(floatFieldSelector);
    rectangularSelection({ x: 0.7, y: 0.05 }, { x: 1, y: 0.15 });  // Select boxes "67.89" and "12"
    // Selecting multiple values on a float field is invalid, the value should remain unchanged
    await contains(floatFieldSelector, { value: "123.45" });

    rectangularSelection({ x: 0.9, y: 0.05 }, { x: 1, y: 0.15 });  // Select box "12"
    await contains(floatFieldSelector, { value: "12.00" });

    await unfocusField(floatFieldSelector);

    // **** Integer field ****
    const integerFieldSelector = ".o_field_widget[name=integer_field] input";
    await focusField(integerFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["number"][0].length });

    await clickOnBox(123.45);
    await contains(integerFieldSelector, { value: "123" });

    await focusField(integerFieldSelector);
    rectangularSelection({ x: 0.7, y: 0.05 }, { x: 1, y: 0.15 });  // Select boxes "67.89" and "12"
    // Selecting multiple values on a integer field is invalid, the value should remain unchanged
    await contains(integerFieldSelector, { value: "123" });

    rectangularSelection({ x: 0.9, y: 0.05 }, { x: 1, y: 0.15 });  // Select box "12"
    await contains(integerFieldSelector, { value: "12" });

    await unfocusField(integerFieldSelector);

    // **** Monetary field ****
    const monetaryFieldSelector = ".o_field_widget[name=monetary_field] input";
    await focusField(monetaryFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["number"][0].length });

    await clickOnBox(123.45);
    await contains(monetaryFieldSelector, { value: "123.45" });

    await focusField(monetaryFieldSelector);
    rectangularSelection({ x: 0.7, y: 0.05 }, { x: 1, y: 0.15 });  // Select boxes "67.89" and "12"
    // Selecting multiple values on a monetary field is invalid, the value should remain unchanged
    await contains(monetaryFieldSelector, { value: "123.45" });

    rectangularSelection({ x: 0.9, y: 0.05 }, { x: 1, y: 0.15 });  // Select box "12"
    await contains(monetaryFieldSelector, { value: "12.00" });

    await unfocusField(monetaryFieldSelector);

    // **** Date field ****
    const dateFieldSelector = ".o_field_widget[name=date_field] input";
    await focusField(dateFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["date"][0].length });

    await clickOnBox("2020-01-01");
    await contains(dateFieldSelector, { value: "01/01/2020" });

    rectangularSelection({ x: 0.45, y: 0.15 }, { x: 0.75, y: 0.37 });  // Select boxes "2020-01-15" and "2020-01-03"
    // Selecting multiple values on a date field is invalid, the value should remain unchanged
    await contains(dateFieldSelector, { value: "01/01/2020" });

    rectangularSelection({ x: 0.45, y: 0.15 }, { x: 0.75, y: 0.25 });  // Select box "2020-01-15"
    await contains(dateFieldSelector, { value: "01/15/2020" });
    await unfocusField(dateFieldSelector);

    // **** Datetime field ****
    const datetimeFieldSelector = ".o_field_widget[name=datetime_field] input";
    await focusField(datetimeFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["date"][0].length });

    await clickOnBox("2020-01-01");
    await contains(datetimeFieldSelector, { value: "01/01/2020 00:00:00" });

    await focusField(datetimeFieldSelector);
    rectangularSelection({ x: 0.45, y: 0.15 }, { x: 0.75, y: 0.37 });  // Select boxes "2020-01-15" and "2020-01-03"
    // Selecting multiple values on a datetime field is invalid, the value should remain unchanged
    await contains(datetimeFieldSelector, { value: "01/01/2020 00:00:00" });

    rectangularSelection({ x: 0.45, y: 0.15 }, { x: 0.75, y: 0.25 });  // Select box "2020-01-15"
    await contains(datetimeFieldSelector, { value: "01/15/2020 00:00:00" });

    await unfocusField(datetimeFieldSelector);

    // **** Many2one field ****
    const many2oneFieldSelector = ".o_field_widget[name=partner_id] input";
    await focusField(many2oneFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["word"][0].length });

    rectangularSelection({ x: 0.15, y: 0.05 }, { x: 0.45, y: 0.15 });  // Select boxes "Hello" and "world"
    await contains(many2oneFieldSelector, { value: "Hello world partner" });

    await unfocusField(many2oneFieldSelector);

    // **** Currency field ****
    const currencyFieldSelector = ".o_field_widget[name=currency_id] input";
    await focusField(currencyFieldSelector);
    await contains(".o_extract_mixin_box", { count: boxes["word"][0].length });

    await clickOnBox("USD");
    await expect.verifySteps(['get_currency_from_text']);
    await contains(currencyFieldSelector, { value: "USD" });

    await unfocusField(currencyFieldSelector);

    // **** One2many field ****
    await click(".o_field_x2many_list_row_add button");
    await waitFor(".o_extract_mixin_box", { timeout: 2000 });

    // Check that clicking on a box works properly
    await focusField(".o_field_one2many .o_field_widget[name=float_field] input");
    await contains(".o_extract_mixin_box", { count: boxes["number"][0].length });
    await clickOnBox(123.45);
    await contains(".o_field_one2many .o_field_widget[name=float_field] input", { value: "123.45" });

    // Fill the float column
    await focusField(".o_field_one2many .o_field_widget[name=float_field] input");
    await contains(".o_extract_mixin_box", { count: boxes["number"][0].length });
    rectangularSelection({ x: 0.85, y: 0.3 }, { x: 1, y: 0.65 }); // Select the column of 5 numbers
    await contains(".o_field_one2many tr.o_data_row", { count: 5 });  // A line should be created for each number
    await contains(".o_field_one2many .o_field_widget[name=float_field] input", { value: "28.08" });
    await contains(".o_field_one2many tr:nth-of-type(2) td[name=float_field]", { textContent: "19.95" });
    await contains(".o_field_one2many tr:nth-of-type(3) td[name=float_field]", { textContent: "12.00" });
    await contains(".o_field_one2many tr:nth-of-type(4) td[name=float_field]", { textContent: "168.21" });
    await contains(".o_field_one2many tr:nth-of-type(5) td[name=float_field]", { textContent: "0.57" });
    await unfocusField(".o_field_one2many .o_field_widget[name=float_field] input");

    // Fill the char column
    await focusField(".o_field_one2many .o_field_widget[name=char_field] input");
    await contains(".o_extract_mixin_box", { count: boxes["word"][0].length });
    rectangularSelection({ x: 0, y: 0.3 }, { x: 0.4, y: 0.65 });  // Select the column of descriptions
    await contains(".o_field_one2many tr.o_data_row", { count: 5 });  // No additional lines should be created
    await contains(".o_field_one2many .o_field_widget[name=char_field] input", { value: "First line" });
    await contains(".o_field_one2many tr:nth-of-type(2) td[name=char_field]", { textContent: "Second line with continuation line" });
    await contains(".o_field_one2many tr:nth-of-type(3) td[name=char_field]", { textContent: "Third line" });
    await contains(".o_field_one2many tr:nth-of-type(4) td[name=char_field]", { textContent: "Fourth line" });
    await contains(".o_field_one2many tr:nth-of-type(5) td[name=char_field]", { textContent: "Fifth line" });
    await focusField(".o_field_one2many .o_field_widget[name=char_field] input");

    // Fill the date column by clicking on the column button
    await focusField(".o_field_one2many .o_field_widget[name=date_field] input");
    await contains(".o_extract_mixin_box", { count: boxes["date"][0].length });
    await click(".o_extract_mixin_box_cluster_button");  // Click on the column of dates
    await contains(".o_field_one2many tr.o_data_row", { count: 5 });  // No additional lines should be created
    await contains(".o_field_one2many .o_field_widget[name=date_field] input", { value: "01/03/2020" });
    await contains(".o_field_one2many tr:nth-of-type(2) td[name=date_field]", { textContent: "Jan 7, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(3) td[name=date_field]", { textContent: "Jan 13, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(4) td[name=date_field]", { textContent: "Jan 14, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(5) td[name=date_field]", { textContent: "Jan 15, 2020" });
    await unfocusField(".o_field_one2many .o_field_widget[name=date_field] input");

    // Manually fill the daterange start date column
    await editInput(document.body, ".o_field_one2many tr:nth-of-type(1) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)", "01/01/2020");
    await click(".o_field_one2many tr:nth-of-type(2) .o_field_widget[name=daterange_field_start]");
    await animationFrame();
    await editInput(document.body, ".o_field_one2many tr:nth-of-type(2) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)", "01/01/2020");
    await click(".o_field_one2many tr:nth-of-type(3) .o_field_widget[name=daterange_field_start]");
    await animationFrame();
    await editInput(document.body, ".o_field_one2many tr:nth-of-type(3) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)", "01/01/2020");
    await click(".o_field_one2many tr:nth-of-type(4) .o_field_widget[name=daterange_field_start]");
    await animationFrame();
    await editInput(document.body, ".o_field_one2many tr:nth-of-type(4) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)", "01/01/2020");
    await click(".o_field_one2many tr:nth-of-type(5) .o_field_widget[name=daterange_field_start]");
    await animationFrame();
    await editInput(document.body, ".o_field_one2many tr:nth-of-type(5) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)", "01/01/2020");

    // // Fill the daterange end date column
    await focusField(".o_field_one2many .o_field_widget[name=daterange_field_start] input:nth-of-type(2)");
    await contains(".o_extract_mixin_box", { count: boxes["date"][0].length });
    await click(".o_extract_mixin_box_cluster_button");  // Click on the column of dates
    await animationFrame();
    await contains(".o_field_one2many tr:nth-of-type(1) .o_field_widget[name=daterange_field_start] span:first-child", { textContent: "Jan 1, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(1) .o_field_widget[name=daterange_field_start] span:nth-of-type(2)", { textContent: "Jan 3, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(2) .o_field_widget[name=daterange_field_start] span:first-child", { textContent: "Jan 1, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(2) .o_field_widget[name=daterange_field_start] span:nth-of-type(2)", { textContent: "Jan 7, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(3) .o_field_widget[name=daterange_field_start] span:first-child", { textContent: "Jan 1, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(3) .o_field_widget[name=daterange_field_start] span:nth-of-type(2)", { textContent: "Jan 13, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(4) .o_field_widget[name=daterange_field_start] span:first-child", { textContent: "Jan 1, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(4) .o_field_widget[name=daterange_field_start] span:nth-of-type(2)", { textContent: "Jan 14, 2020" });
    await contains(".o_field_one2many tr:nth-of-type(5) .o_field_widget[name=daterange_field_start] button:nth-of-type(1)", { value: "01/01/2020" });
    await contains(".o_field_one2many tr:nth-of-type(5) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)", { value: "01/15/2020" });
    await unfocusField(".o_field_one2many tr:nth-of-type(5) .o_field_widget[name=daterange_field_start] input:nth-of-type(1)");
});

test("focusing on a nested widget inside a json field does not crash", async () => {
    const pyEnv = await startServer();
    const recordId = pyEnv["iap_extract.manual.correction"].create({
        extract_state: "waiting_validation",
    });
    const irAttachmentId = pyEnv["ir.attachment"].create({
        name: "test_image.png",
        res_model: "iap_extract.manual.correction",
        res_id: recordId,
        mimetype: "image/png",
    });
    pyEnv["iap_extract.manual.correction"].write([recordId], {
        extract_attachment_id: irAttachmentId,
    });
    pyEnv["mail.message"].create({
        attachment_ids: [irAttachmentId],
        model: "iap_extract.manual.correction",
        res_id: recordId,
    });

    onRpc("iap_extract.manual.correction", "get_boxes", () => {
        return boxes;
    });

    await start();
    await openFormView("iap_extract.manual.correction", recordId, {
        arch: `
        <form js_class="manual_correction_form">
            <sheet>
                <group>
                    <field name="extract_state"/>
                    <field name="extract_attachment_id"/>
                    <field name="json_field"/>
                </group>
            </sheet>
            <div class="o_attachment_preview"/>
            <chatter/>
        </form>`,
    });
    await contains(".o-mail-Attachment-imgContainer");

    // Simulate the DOM structure created by widgets like AnalyticDistribution,
    // which render nested .o_field_widget elements inside a json field.
    const jsonWidget = queryFirst(".o_field_widget[name=json_field]");
    const nestedWidget = document.createElement("div");
    nestedWidget.className = "o_field_widget";
    nestedWidget.setAttribute("name", "nested_sub_field");
    const nestedInput = document.createElement("input");
    nestedWidget.appendChild(nestedInput);
    jsonWidget.appendChild(nestedWidget);

    // Focusing on the nested input triggers getBoxType("json_field.nested_sub_field").
    // Without the fix, this crashes because a json field has no _config property
    // (only relational fields backed by StaticList/DataPoint have _config).
    nestedInput.focus();
    await waitForNone(".o_extract_mixin_box", { timeout: 2000 });
    await contains(".o_extract_mixin_box", { count: 0 });
});
