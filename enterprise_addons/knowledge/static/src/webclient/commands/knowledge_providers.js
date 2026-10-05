import { markup, usePlugin, t, useProps } from "@odoo/owl";
import { DefaultCommandItem, defaultCommandItemProps } from "@web/core/commands/command_palette";
import { HotkeyCommandItem } from "@web/core/commands/default_providers";
import { _t } from "@web/core/l10n/translation";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { highlightText } from "@web/core/utils/html";

// Articles command
class KnowledgeCommand extends DefaultCommandItem {
    static template = "knowledge.KnowledgeCommandTemplate";
    props = useProps({
        ...defaultCommandItemProps,
        headline: t.string(),
        icon_string: t.string(),
        isFavorite: t.boolean(),
        subjectText: t.string(),
        subjectName: t.or([t.string(), t.boolean()]),
    });
}

// "Not found, create one" command
class Knowledge404Command extends DefaultCommandItem {
    static template = "knowledge.Knowledge404CommandTemplate";
    props = useProps({
        ...defaultCommandItemProps,
        articleName: t.string(),
    });
}

// Advanced search command
class KnowledgeExtraCommand extends HotkeyCommandItem {
    static template = "knowledge.KnowledgeExtraCommandTemplate";
}

const commandSetupRegistry = registry.category("command_setup");
commandSetupRegistry.add("?", {
    debounceDelay: 500,
    emptyMessage: _t("No article found."),
    name: _t("articles"),
    placeholder: _t("Search for an article or a keyword..."),
});

const commandProviderRegistry = registry.category("command_provider");

const fn = (hidden) => {
    // Check if the user has enough rights to create a new article
    const canCreate = () => user.checkAccessRight("knowledge.article", "create");
    let articlesData;
    return async function provide(options) {
        const action = useService("action");
        const orm = usePlugin(ORM);

        articlesData = await orm.call(
            "knowledge.article",
            "get_user_sorted_articles",
            [[]],
            {
                search_query: options.searchValue,
                hidden_mode: hidden,
            }
        );
        if (!hidden){
            if (articlesData.length === 0) {
                // Only display the "create article" command when the user can
                // create an article and when the user inputs at least 3 characters
                if (options.searchValue.length > 2 && await canCreate()) {
                    return [{
                        Component: Knowledge404Command,
                        async action() {
                            const articleIds = await orm.call(
                                'knowledge.article',
                                'article_create',
                                [options.searchValue],
                                {
                                    is_private: true
                                },
                            );

                            action.doAction('knowledge.ir_actions_server_knowledge_home_page', {
                                additionalContext: {
                                    res_id: articleIds[0],
                                }
                            });
                        },
                        name: _t('No Article found. Create "%s"', options.searchValue),
                        props: {
                            articleName: options.searchValue,
                        },
                    }];
                }
                else {
                    return [];
                }
            }
        }
        // display the articles
        const result = articlesData.map(article => ({
            Component: KnowledgeCommand,
            action() {
                action.doAction('knowledge.ir_actions_server_knowledge_home_page', {
                    additionalContext: {
                        res_id: article.id,
                    }
                });

            },
            category: "knowledge_articles",
            href: `/odoo/knowledge.article/${article.id}`,
            name: article.name || _t("Untitled"),
            props: {
                isFavorite: article.is_user_favorite,
                headline: article.headline ? markup(article.headline) : "",
                subjectName:
                    article.root_article_id[0] != article.id ? article.root_article_id[1] : false,
                subjectText: highlightText(
                    options.searchValue,
                    article.root_article_id[1],
                    "fw-bolder text-primary"
                ),
                icon_string: article.icon || "",
            },
        }));
        if (!hidden && !(await user.hasGroup("base.group_portal"))) {
            // add the "advanced search" command
            result.push({
                Component: KnowledgeExtraCommand,
                async action() {
                    const articleIds = articlesData.map(article => article.id);
                    const actionDescr = await action.loadAction('knowledge.knowledge_article_action');
                    delete actionDescr.context.search_default_filter_not_is_article_item;
                    action.doAction(actionDescr, {
                        additionalContext: {
                            search_default_filter_search_article_ids: 1,
                            search_article_ids: articleIds,
                        },
                    });
                },
                category: "knowledge_extra",
                name: _t("Advanced Search"),
                props: {
                    hotkey: "alt+B",
                },
            });
        }
        return result;
    };
};

commandProviderRegistry.add("knowledge", {
    debounceDelay: 500,
    namespace: "?",
    provide: fn(false),
});

commandSetupRegistry.add("$", {
    debounceDelay: 500,
    emptyMessage: _t("Oops, there's nothing here. Try another search."),
    placeholder: _t("Search hidden Articles..."),
});
commandProviderRegistry.add("knowledge_members_only_articles", {
    debounceDelay: 500,
    namespace: "$",
    provide: fn(true),
});
