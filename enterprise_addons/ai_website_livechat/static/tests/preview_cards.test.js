import { AIRecordsPreview } from "@ai_website_livechat/discuss/core/common/preview_records/ai_records_preview";
import { previewCardsCache } from "@ai_website_livechat/discuss/core/common/preview_records/use_ai_preview_cards";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import { expect, getFixture, test } from "@odoo/hoot";
import { click, waitFor } from "@odoo/hoot-dom";
import {
    mountWithCleanup,
    mockService,
    onRpc,
    patchWithCleanup,
    preventResizeObserverError,
} from "@web/../tests/web_test_helpers";

preventResizeObserverError();
defineMailModels();

test("AIRecordsPreview fetches and injects preview cards", async () => {
    previewCardsCache.invalidate();
    mockService("public.interactions", () => ({
        startInteractions(root) {
            expect.step(`start:${root.querySelectorAll(".o_ai_preview_card").length}`);
        },
        stopInteractions() {},
    }));
    onRpc("/ai/preview_cards", async (request) => {
        const { params } = await request.json();
        expect.step("fetch-cards");
        expect(params).toEqual({ model: "product.template", record_ids: [10, 11] });
        return {
            count: 2,
            html: `
                <div class="o_ai_preview_cards">
                    <div class="o_ai_preview_card" data-href="/shop/product/desk">
                        <a href="/shop/product/desk">Desk</a>
                    </div>
                    <div class="o_ai_preview_card" data-href="/shop/product/chair">
                        <button type="button">Configure</button>
                        <a class="o_add_wishlist" href="/shop/wishlist">Wishlist</a>
                    </div>
                </div>
            `,
        };
    });

    const message = {
        id: 42,
        ai_record_previews: {
            preview_sets: [
                {
                    preview_key: 0,
                    model: "product.template",
                    has_preview_cards: true,
                    records: [
                        { id: 10, url: "/shop/product/desk", name: "Desk" },
                        { id: 11, url: "/shop/product/chair", name: "Chair" },
                    ],
                    header: "",
                },
            ],
        },
    };
    const fixture = getFixture();
    fixture.innerHTML = `
        <div class="o_ai_livechat_message_content">
            <span class="o_ai_preview_data">
                <a href="/shop/product/desk">Desk</a>
                <a href="/shop/product/chair">Chair</a>
            </span>
        </div>
    `;
    await mountWithCleanup(AIRecordsPreview, {
        target: fixture.querySelector(".o_ai_livechat_message_content"),
        props: { message },
    });

    await waitFor(".o_ai_preview_cards_wrapper");
    expect(".o_ai_preview_card").toHaveCount(2);
    expect(".o_ai_preview_data").not.toBeVisible();
    expect(".o_ai_preview_card a[href='/shop/product/desk']").toHaveAttribute("target", "_blank");
    expect(".o_ai_preview_card a[href='/shop/product/desk']").toHaveAttribute(
        "rel",
        "noopener noreferrer"
    );
    expect.verifySteps(["fetch-cards", "start:2"]);
});

test("AIRecordsPreview opens plain card clicks and leaves controls alone", async () => {
    previewCardsCache.invalidate();
    mockService("public.interactions", () => ({
        startInteractions() {},
        stopInteractions() {},
    }));
    onRpc("/ai/preview_cards", () => ({
        count: 2,
        html: `
            <div class="o_ai_preview_cards">
                <div class="o_ai_preview_card" data-href="/shop/product/desk">
                    <span class="plain">Desk</span>
                </div>
                <div class="o_ai_preview_card" data-href="/shop/product/chair">
                    <button type="button">Configure</button>
                    <a href="/shop/product/chair">Chair</a>
                    <a class="badge text-bg-primary" href="/slides/course/tag/tools">Tools</a>
                    <a class="badge post_link text-decoration-none o_tag o_color_1" href="/blog">Blog</a>
                </div>
            </div>
        `,
    }));
    patchWithCleanup(window, {
        open(url, target, features) {
            expect.step(`${url}:${target}:${features}`);
        },
    });

    const message = {
        id: 43,
        ai_record_previews: {
            preview_sets: [
                {
                    preview_key: 0,
                    model: "product.template",
                    has_preview_cards: true,
                    records: [
                        { id: 10, url: "/shop/product/desk", name: "Desk" },
                        { id: 11, url: "/shop/product/chair", name: "Chair" },
                    ],
                    header: "",
                },
            ],
        },
    };
    const fixture = getFixture();
    fixture.innerHTML = `
        <div class="o_ai_livechat_message_content">
            <span class="o_ai_preview_data">
                <a href="/shop/product/desk">Desk</a>
                <a href="/shop/product/chair">Chair</a>
            </span>
        </div>
    `;
    await mountWithCleanup(AIRecordsPreview, {
        target: fixture.querySelector(".o_ai_livechat_message_content"),
        props: { message },
    });
    await waitFor(".o_ai_preview_card .plain");

    expect(".o_ai_preview_inert_control").toHaveCount(1);
    expect(".o_ai_preview_inert_control").not.toHaveAttribute("href");
    expect(".o_ai_preview_card .post_link").toHaveCount(0);

    await click(".o_ai_preview_card .plain");
    await click(".o_ai_preview_card button");
    await click(".o_ai_preview_card a[href='/shop/product/chair']");
    await click(".o_ai_preview_inert_control");

    expect.verifySteps(["/shop/product/desk:_blank:noopener"]);
});

test("AIRecordsPreview shows links for non-previewable records", async () => {
    const fixture = getFixture();
    fixture.innerHTML = `
        <div class="o_ai_livechat_message_content">
            <span class="o_ai_preview_data">
                <a href="/web#model=res.partner&amp;id=7">Azure Interior</a>
            </span>
        </div>
    `;

    await mountWithCleanup(AIRecordsPreview, {
        target: fixture.querySelector(".o_ai_livechat_message_content"),
        props: {
            message: {
                id: 44,
                ai_record_previews: {
                    preview_sets: [
                        {
                            preview_key: 0,
                            model: "res.partner",
                            has_preview_cards: false,
                            records: [
                                {
                                    id: 7,
                                    url: "/web#model=res.partner&id=7",
                                    name: "Azure Interior",
                                },
                            ],
                            header: "",
                        },
                    ],
                },
            },
        },
    });

    expect(".o_ai_preview_cards_wrapper").toHaveCount(0);
    expect(".o_ai_record_previews .o_ai_preview_link a").toHaveText("Azure Interior");
    expect(".o_ai_record_previews .o_ai_preview_link a").toBeVisible();
    expect(".o_ai_preview_data").not.toBeVisible();
});

test("AIRecordsPreview shows links fallback when fetched HTML has no cards", async () => {
    previewCardsCache.invalidate();
    mockService("public.interactions", () => ({
        startInteractions() {},
        stopInteractions() {},
    }));
    onRpc("/ai/preview_cards", () => {
        expect.step("fetch-empty");
        return {
            count: 0,
            html: `<div class="o_ai_preview_cards"></div>`,
        };
    });

    const fixture = getFixture();
    fixture.innerHTML = `
        <div class="o_ai_livechat_message_content">
            <span class="o_ai_preview_data"><a href="/shop/product/desk">Desk</a></span>
        </div>
    `;

    await mountWithCleanup(AIRecordsPreview, {
        target: fixture.querySelector(".o_ai_livechat_message_content"),
        props: {
            message: {
                id: 46,
                ai_record_previews: {
                    preview_sets: [
                        {
                            preview_key: 0,
                            model: "product.template",
                            has_preview_cards: true,
                            records: [{ id: 10, url: "/shop/product/desk", name: "Desk" }],
                            header: "",
                        },
                    ],
                },
            },
        },
    });

    await waitFor(".o_ai_record_previews .o_ai_preview_link a[href='/shop/product/desk']");
    expect(".o_ai_preview_cards_wrapper").toHaveCount(0);
    // Falls back to links since cards fetch returned empty
    expect(".o_ai_record_previews .o_ai_preview_link a[href='/shop/product/desk']").toHaveText(
        "Desk"
    );
    expect(".o_ai_preview_data").not.toBeVisible();
    expect.verifySteps(["fetch-empty"]);
});
