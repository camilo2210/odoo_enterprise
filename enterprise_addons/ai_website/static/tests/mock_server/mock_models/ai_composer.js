import { AIComposer, INTERFACE_KEYS } from "@ai/../tests/mock_server/mock_models/ai_composer";
import { fields } from "@web/../tests/web_test_helpers";

export class WebsiteAIComposer extends AIComposer {
    interface_key = fields.Selection({
        selection: [
            ...INTERFACE_KEYS,
            ["website_seo_ai", "Website SEO AI"],
            ["website_builder_ai", "Website Builder AI"],
        ],
    });
}
