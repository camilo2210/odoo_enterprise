import { Component, xml, proxy, useProps, t } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { Article } from "@website_knowledge/frontend/knowledge_public_view/knowledge_public_article";
import { KnowledgePublicSidebar } from "@website_knowledge/frontend/sidebar/knowledge_public_sidebar";
import { KnowledgeReadOnlyHeadingLink } from "@knowledge/components/knowledge_readonly_heading_link/knowledge_readonly_heading_link";
import { patch } from "@web/core/utils/patch";
import { router } from "@web/core/browser/router";
import { location } from "@web/core/browser/browser";
import { stateToUrl, urlToState } from "@knowledge/portal_webclient/router_utils";

const SIDEBAR_ENABLE_BUTTON_SELECTOR = ".o_knowledge_sidebar_enabler_button";
const contentTemplate = xml`<t t-out="this.content"/>`;

class HeadingLinkLocalOverlay extends Component {
    static template = xml`<div class="o-public-local-overlay position-relative h-0 w-0">
        <KnowledgeReadOnlyHeadingLink readonlyElementRef="this.props.readonlyElementRef"/>
    </div>`;
    static components = {
        KnowledgeReadOnlyHeadingLink,
    };

    props = useProps({
        readonlyElementRef: t.function([], t.ref()),
    });
}

export class KnowledgePublicViewInteraction extends Interaction {
    static selector = ".o_knowledge_public_view";
    dynamicContent = {
        _root: {
            "t-att-data-res_id": () => this.subEnv.record.resId,
        },
        [SIDEBAR_ENABLE_BUTTON_SELECTOR]: {
            "t-on-click": () => {
                this.subEnv.toggleSidebar(true);
            },
        },
        ".o_knowledge_sidebar_container": {
            "t-component": () => {
                const el = this.el.querySelector(".o_knowledge_sidebar_container");
                return [
                    KnowledgePublicSidebar,
                    {
                        onMounted: () => {
                            el.classList.remove("o_knowledge_sidebar_loading");
                        },
                        subEnv: this.subEnv,
                        viewState: this.state,
                    },
                ];
            },
        },
        ".o_knowledge_article_log_in": {
            "t-att-href": () =>
                `/web/login?redirect=/knowledge/article/${this.subEnv.record.resId}`,
        },
        ".o_knowledge_article": {
            "t-component": (target) => [
                HeadingLinkLocalOverlay,
                {
                    readonlyElementRef: () => target.querySelector(".o_readonly"),
                },
            ],
        },
    };

    setup() {
        this.interactionService = this.services["public.interactions"];
        this.uiService = this.services.ui;
        this.state = proxy({
            showSidebar: false,
        });
        const handleButtonVisibility = () => {
            const button = this.el.querySelector(SIDEBAR_ENABLE_BUTTON_SELECTOR);
            button?.classList[this.state.showSidebar ? "add" : "remove"]("d-none");
        };
        this.subEnv = {
            record: new Article(parseInt(this.el.dataset.res_id)),
            openArticle: async (articleId) => {
                await this.waitFor(this.subEnv.record.load(articleId));
                const container = this.el.querySelector(".o_knowledge_public_content_container");
                this.interactionService.stopInteractions(container);
                container.replaceChildren();
                // Interactions are restarted during the renderAt process.
                this.renderAt(contentTemplate, { content: this.subEnv.record.content }, container);
                if (this.uiService.isSmall) {
                    this.subEnv.toggleSidebar(false);
                } else {
                    handleButtonVisibility();
                }
            },
            toggleSidebar: (showSidebar) => {
                showSidebar ??= !this.state.showSidebar;
                this.state.showSidebar = showSidebar;
                handleButtonVisibility();
            },
        };
        this.unpatchRouter = patch(router, {
            stateToUrl,
            urlToState,
        });
        router.replaceState(router.urlToState(new URL(location)));
    }

    async willStart() {
        if (this.el.querySelector(".o_knowledge_sidebar_container")) {
            this.subEnv.toggleSidebar(!this.uiService.isSmall);
        }
    }

    destroy() {
        this.unpatchRouter();
    }
}

registry
    .category("public.interactions")
    .add("website_knowledge.article_public_view", KnowledgePublicViewInteraction);
