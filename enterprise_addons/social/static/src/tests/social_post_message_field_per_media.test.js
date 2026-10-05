import { expect, test } from "@odoo/hoot";
import { queryOne } from "@odoo/hoot-dom";
import { runAllTimers } from "@odoo/hoot-mock";

import { defineMailModels, insertText } from "@mail/../tests/mail_test_helpers";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    pagerNext,
} from "@web/../tests/web_test_helpers";

class SocialAccount extends models.Model {
    _name = "social.account";

    search_mention_suggestions(searchValue, mediaType) {
        if (mediaType === "twitter") {
            return [
                {
                    name: "User",
                    username: "UserName",
                    description: `A Full description of the user. You searched for ${searchValue}`,
                },
            ];
        }
    }
}

class SocialLivePost extends models.Model {
    _name = "social.live.post";

    body = fields.Text();
    max_post_length_per_media = fields.Json();
    social_post_mentions = fields.Text();
    is_split_per_media = fields.Boolean();

    _views = {
        form: `<form>
            <field name="is_split_per_media" invisible="1"/>
            <field name="max_post_length_per_media" invisible="1"/>
            <field name="social_post_mentions"/>
            <field name="body" widget="social_post_message_field" social_media="twitter" onchange_on_keydown="True"/>
        </form>`,
    };

    _records = [
        {
            id: 1,
            is_split_per_media: true,
            body: "A",
            max_post_length_per_media: [{ mediaId: 1, mediaType: "twitter", maxPostLength: 280 }],
        },
        {
            id: 2,
            is_split_per_media: true,
            social_post_mentions: '{"twitter":{"Norbert":"albert"}}',
            body: "Welcome @Norbert",
            max_post_length_per_media: [{ mediaId: 1, mediaType: "twitter", maxPostLength: 280 }],
        },
        {
            id: 3,
            is_split_per_media: true,
            max_post_length_per_media: [{ mediaId: 1, mediaType: "twitter", maxPostLength: 280 }],
        },
    ];
}
defineModels([SocialAccount, SocialLivePost]);
defineMailModels();

test("normal detection and replacement systems", async () => {
    await mountView({
        resId: 3,
        type: "form",
        resModel: "social.live.post",
    });
    await insertText("textarea#body_0", "Hello @user");
    await runAllTimers();
    await contains(
        ".o-mail-NavigableList-item:has(em.o_social_mention_option_description)"
    ).click();
    await expect(queryOne("textarea#body_0").value).toBe("Hello @UserName ");
    await expect(queryOne(".o_field_social_count span").textContent).toBe("264");
    await expect(
        JSON.parse(queryOne("textarea#social_post_mentions_0").value).twitter
    ).toMatchObject({ UserName: "UserName" });
});

test("message count follows the active record", async () => {
    await mountView({
        resId: 1,
        resIds: [1, 2],
        type: "form",
        resModel: "social.live.post",
    });
    await expect(queryOne(".o_field_social_count span").textContent).toBe("279");
    await pagerNext();
    await expect(queryOne(".o_field_social_count span").textContent).toBe("264");
});

test("update mentions if mention is removed", async () => {
    await mountView({
        resId: 2,
        resModel: "social.live.post",
        type: "form",
    });
    await expect(
        JSON.parse(queryOne("textarea#social_post_mentions_0").value)["twitter"]
    ).toMatchObject({ Norbert: "albert" });
    await contains("textarea#body_0").edit("Hello World!");
    await runAllTimers();
    await expect(
        JSON.parse(queryOne("textarea#social_post_mentions_0").value)["twitter"]
    ).toMatchObject({});
});
