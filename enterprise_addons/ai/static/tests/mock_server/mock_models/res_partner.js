import { fields, models } from "@web/../tests/web_test_helpers";

export class Partner extends models.Model {
    name = fields.Char();
    foo = fields.Char();

    _records = [{ id: 1, name: "dummy record", foo: "yop" }];
    _views = {
        kanban: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="foo"/>
                    </t>
                </templates>
            </kanban>
        `,
        list: `
            <list>
                <field name="foo"/>
            </list>
        `,
    };
}
