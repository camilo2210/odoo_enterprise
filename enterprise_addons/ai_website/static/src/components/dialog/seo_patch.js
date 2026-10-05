import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { TitleDescription, OptimizeSEODialog, seoContext } from "@website/components/dialog/seo";

const SCHEMA = {
    type: "object",
    properties: {
        title: {
            type: "string",
            description: "The title of the web page.",
            minLength: 50,
        },
        description: {
            type: "string",
            description: "The description of the web page.",
            minLength: 100,
        },
        keywords: {
            type: "array",
            description: "A list of relevant keyword based on the web page content.",
            items: {
                type: "string",
            },
            maxItems: 10,
        },
    },
    required: ["title", "description", "keywords"],
    additionalProperties: false,
};

const getAISeo = async (component, onlyKeywords = false) => {
    /** @type{HTMLElement} */
    const pageTextContentEl = component.website.pageDocument.documentElement.querySelector("main");

    // Filtering down on actual interesting elements for seo
    // getting rid of noise for the agent
    const textElements = pageTextContentEl.querySelectorAll("h1, h2, h3, a, p");

    // We only keep elements that are visible to the user
    // since it would most likely be what the user would
    // use if he had to do SEO manually
    let pageContentStr = "";
    textElements.forEach((element) => {
        const isVisible = element.checkVisibility({
            checkOpacity: true,
            checkVisibilityCSS: true,
        });
        if (!isVisible) {
            return;
        }
        pageContentStr += `\n\n${element.outerHTML}`;
    });

    const seoOutput = await rpc("/ai/get_direct_response", {
        interface_key: "website_seo_ai",
        prompt: JSON.stringify({
            website_name: component.website.currentWebsite.name,
            language: component.website.currentWebsite.metadata.lang,
            website_content: pageContentStr,
        }),
        schema: SCHEMA,
    });

    const parsedOutput = JSON.parse(seoOutput);

    if (parsedOutput.keywords.length > 0) {
        component.seoContext.keywords = parsedOutput.keywords;
    }
    if (!onlyKeywords) {
        component.seoContext.title = parsedOutput.title;
        component.seoContext.description = parsedOutput.description;
    }
};

patch(TitleDescription.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },
    async autoFill() {
        await getAISeo(this);
    },
});

patch(OptimizeSEODialog.prototype, {
    async save() {
        const metaImageSrc = seoContext.metaImage;
        if (metaImageSrc) {
            const match = metaImageSrc.match(/\/web\/image\/(\d+)-/);
            if (match) {
                await this.orm.call("ai.attachment.vacuum", "mark_attachments_used", [], {
                    attachment_ids: [parseInt(match[1])],
                });
            }
        }
        await super.save();
    },
});
