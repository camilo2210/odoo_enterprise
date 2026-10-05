import { mailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

class PhoneNumber extends models.Model {
    phone = fields.Char();
    country_id = fields.Many2one({ relation: "res.country" });
    country_flag_url = fields.Char();
    _records = [
        {
            id: 1,
            phone: "+12025550199",
            country_id: 1,
            country_flag_url: "/base/static/img/country_flags/us.png",
        },
    ];
}

defineModels({ ...mailModels, PhoneNumber });

test("phone flags load the country name even when the country column is hidden", async () => {
    mailModels.ResCountry._records = [{ id: 1, name: "United States" }];
    await mountView({
        type: "list",
        resModel: "phone.number",
        arch: `<list>
            <field name="phone" widget="voip_flag_phone"/>
            <field name="country_flag_url" column_invisible="True"/>
            <field name="country_id" column_invisible="True"/>
        </list>`,
    });

    expect("[name=phone] img").toHaveAttribute("alt", "United States flag");
    expect("[name=phone] img").toHaveAttribute("data-tooltip", "United States");
});
