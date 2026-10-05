import { expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { Component, xml, useProps, types } from "@odoo/owl";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { JsonTagsField } from "@obox/widgets/json_tags_field";

class JsonTagsFieldTester extends Component {
    static components = { JsonTagsField };
    static template = xml`
            <JsonTagsField name="'services'" record="this.record"/>
        `;

    props = useProps({ fakeServices: types.array(types.string()) });

    get record() {
        return {
            data: {
                services: this.props.fakeServices,
            },
        };
    }
}

test("parses array into tags", async () => {
    await mountWithCleanup(JsonTagsFieldTester, {
        props: { fakeServices: ["service1", "service2"] },
    });

    expect(queryAllTexts(".o_tag")).toEqual(["service1", "service2"]);
});

test("limits to 10 tags", async () => {
    await mountWithCleanup(JsonTagsFieldTester, {
        props: { fakeServices: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"] },
    });

    expect(".o_tag").toHaveCount(10);
    expect(queryAllTexts(".o_tag").at(-1)).toBe("+2");
});
