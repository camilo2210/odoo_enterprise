import { NavigableList } from "@mail/core/common/navigable_list";
import {
    EmojisTextField,
    emojisTextField,
} from "@mail/views/web/fields/emojis_text_field/emojis_text_field";
import {
    computed,
    proxy,
    signal,
    t,
    untrack,
    useEffect,
    useListener,
    useProps,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { KeepLast } from "@web/core/utils/concurrency";
import { useService } from "@web/core/utils/hooks";
import { markEventHandled } from "@web/core/utils/misc";
import { useDebounced } from "@web/core/utils/timing";
import { useLayoutEffect } from "@web/owl2/utils";
import { textFieldProps } from "@web/views/fields/text/text_field";

/**
 * This widget enables a simple text field to handle the mentions for social media accounts.
 * This means that when a user tries to mention someone using the respective mention methods for each
 * social media, it is able to provide a search for users/pages/businesses.
 *
 * It uses the same idea as for the chatter:
 *  - It detect that the user is adding an `@` inside of the textarea of the message.
 *  - After detecting at least 2 more characters after it, a search is triggered.
 *  - This search returns an array of results given by a specific social media.
 *      (Each of them uses specific routes and parameters)
 *  - The user then selects one of the results and the text typed in the textarea is then replaced
 *    by the `display_name` of the page/user/business.
 *      (e.g. `fpodoo` will be replaced `Fabien Pinckaers` in the textarea)
 *
 * The rest of the handling is then done by the SocialPostFormatterMixin and the social.post.template model.
 */
export class SocialPostMessageField extends EmojisTextField {
    static template = "social.SocialPostMessageField";
    props = useProps({
        // EmojisTextField adds no props of its own to TextField's.
        ...textFieldProps,
        allowDoubleSpace: t.boolean().optional(),
        socialMediaType: t.string().optional(),
    });
    static components = {
        ...EmojisTextField.components,
        NavigableList,
    };

    messageValue = signal(this.props.record.data[this.props.name] || "");
    count = computed(() => this.messageValue().length);

    setup() {
        super.setup();
        useEffect(() => {
            this.messageValue.set(this.props.record.data[this.props.name] || "");
        });
        this.state = proxy({
            isSuggesting: false,
        });
        this.noMentionFoundIndexes = {};
        this.orm = useService("orm");
        this.optionTemplate = "social.MentionsTemplate";
        this.navigableListOptions = proxy([{}]);
        useListener(window, "click", (ev) => {
            if (!ev.target.closest(".o-mail-NavigableList")) {
                markEventHandled(ev, "composer.onClickTextarea");
            }
        });
        useLayoutEffect(
            (textareaEl) => {
                if (textareaEl) {
                    this.state.width = textareaEl.getBoundingClientRect().width;
                }
            },
            () => [untrack(this.textareaRef)]
        );

        this.searchValue = "";
        this.debouncedSearchUser = useDebounced(() => this.searchUser(), 500);
        this.debouncedUpdateMentionField = useDebounced(
            (text) => this.updateMentionField(text),
            1000
        );
        this.keepLast = new KeepLast();
    }

    /**
     * Used to update the mentions field when typing in the text field. Used to remove unused mentions.
     * @param {String} text Text to be updated
     * @returns {Promise}
     */
    async updateMentionField(text) {
        const allMentions = JSON.parse(this.props.record.data.social_post_mentions || "{}");
        const currentMentions = allMentions[this.props.socialMediaType];
        let needToUpdate = false;
        for (const mention in currentMentions) {
            if (text.indexOf(`@${mention}`) < 0) {
                delete currentMentions[mention];
                needToUpdate = true;
            }
        }
        if (!needToUpdate) {
            return;
        }
        allMentions[this.props.socialMediaType] = currentMentions;
        await this.props.record.update({ social_post_mentions: JSON.stringify(allMentions) });
    }

    clearSearch() {
        this.state.isSuggesting = false;
        this.selectionStart = 0;
        this.searchValue = "";
        this.debouncedSearchUser.cancel();
    }

    /**
     * This method is based on the detection system implemented in the Discuss app to detect a mention
     * in the text field.
     * The principle is simple, when an input is detected on the textarea we go from the position of
     * the user's cursor and move towards the start of the textarea's value.
     *
     * There is 2 modes to this detection system: with and without double space.
     * In some cases we want to allow the user to add spaces to the search, because the name they
     * search can contain one.
     * In this mode, when we find a space the search isn't stopped, we only stop if we see 2 spaces
     * one after another.
     *
     * In the other mode when we find a space, the search is stopped.
     *
     * If we arrive at an index that is present in @see noMentionFoundIndexes then we need to compare
     * the current value with the value in the Object. If the substring from selectionEnd to startIndex
     * is the same in the Object and in the textarea. We stop the detection as we know that this
     * substring won't give us any result from the search.
     *
     * If we find an `@`, we first check if it's the 1st character of the string or if there is a
     * space before it.
     * If that's not the case then we consider that it's not a good candidate for a mention.
     * In the correct candidate case then we extract the substring from the index after the `@` to
     * the user's selection position. And this substring becomes our searchValue for the next step.
     *
     * If none of the above happens, then we continue to walk towards the start of the textarea's value.
     */
    onInputDetectMention() {
        // Don't wait for the blur event to update the chars count
        this.messageValue.set(this.textareaRef().value);

        if (this.navigableListOptions.length) {
            this.navigableListOptions.splice(0, this.navigableListOptions.length);
        }
        // Detect the mention
        const start = this.textareaRef().selectionEnd;
        const text = this.textareaRef().value;
        this.debouncedUpdateMentionField(text);
        // consider the chars before the current cursor position
        if (start === 0) {
            this.clearSearch();
        }
        let spaceAlreadyFound = false;
        for (let index = start - 1; index >= 0; --index) {
            if (this.noMentionFoundIndexes[index]) {
                const [startIndex, searchValue] = this.noMentionFoundIndexes[index];
                if (text.substring(startIndex, index) === searchValue) {
                    return;
                } else {
                    delete this.noMentionFoundIndexes[index];
                }
            }
            if (text[index] === " ") {
                if (spaceAlreadyFound || !this.props.allowDoubleSpace) {
                    this.clearSearch();
                    break;
                }
                spaceAlreadyFound = true;
                continue;
            }
            if (text[index] === "@" && (index === 0 || /\s/.test(text[index - 1]))) {
                if (!this.props.record.data.is_split_per_media) {
                    this.navigableListOptions[0] = {
                        isLoaded: true,
                        label: _t("Split per media to add mentions"),
                    };
                } else {
                    this.navigableListOptions[0] = {
                        label: _t("Searching..."),
                        classList: "o-social-NavigableList-item fst-italic pe-none",
                        unselectable: true,
                    };
                    this.selectionStart = index;
                    this.searchValue = text.substring(index + 1, start);
                }
                const mention = this.searchValue.split(" ")[0];
                this.state.isSuggesting = !JSON.parse(
                    this.props.record.data.social_post_mentions || "{}"
                )[this.props.socialMediaType]?.[mention];
                break;
            } else if (text[index] === "@" && index > 0 && !/\s/.test(text[index - 1])) {
                break;
            } else {
                spaceAlreadyFound = false;
            }
        }
        if (!this.props.record.data.is_split_per_media) {
            return;
        }
        if (this.searchValue.length >= 2 && this.state.isSuggesting) {
            this.keepLast.add(this.debouncedSearchUser());
        } else if (this.searchValue.length < 2) {
            this.state.isSuggesting = false;
        }
    }

    getMentionDisplayName(option) {
        return option.userInfo.username || option.userInfo.name;
    }

    /**
     * This method uses the ORM to call the `search_mention_suggestions` method using the searchValue
     * found in `onInputDetectMention`.
     * Since this method is debounced we need to recheck if we are still searching for a value longer
     * than 2 characters. If that's the case then after the call if we have a result we use it to set
     * the options for the NavigableList so that the user can choose the mention they want.
     *
     * If we don't have any result after the call, then we update the noMentionFoundIndexes object
     * with the user's selection's end position as the key and the value being an Array: [startIndex, mentionFound].
     *
     * This object is used in @see onInputDetectMention
     */
    async searchUser() {
        if (this.searchValue.length < 2) {
            this.navigableListOptions.splice(0, this.navigableListOptions.length);
            this.state.isSuggesting = false;
            return;
        }
        const userInfo = await this.orm.call("social.account", "search_mention_suggestions", [
            this.searchValue,
            this.props.socialMediaType,
        ]);
        if (userInfo.length) {
            this.navigableListOptions.splice(
                0,
                1,
                ...userInfo.map((value) => ({
                    userInfo: value,
                    classList: "o-social-NavigableList-item",
                    isLoaded: true,
                }))
            );
        } else {
            this.noMentionFoundIndexes[this.textareaRef().selectionEnd] = [
                this.selectionStart + 1,
                this.searchValue,
            ];
            this.state.isSuggesting = false;
        }
    }

    async onSelect(ev, option, params) {
        if (!this.props.record.data.is_split_per_media) {
            this.state.isSuggesting = false;
            this.navigableListOptions = proxy([{}]);
            this.textareaRef()?.blur();
            await this.props.record.update({
                [this.props.name]: this.textareaRef().value,
                is_split_per_media: true,
            });
        } else {
            this.state.isSuggesting = false;
            this.navigableListOptions = proxy([{}]);
            if (option.userInfo === undefined) {
                return;
            }
            const selectionEnd = this.textareaRef().selectionEnd;
            const replacedValue = this.getMentionDisplayName(option);
            const textMessage = this.textareaRef().value;

            this.textareaRef().value =
                textMessage
                    .substring(0, selectionEnd)
                    .replace(`@${this.searchValue}`, `@${replacedValue} `) +
                textMessage.substring(selectionEnd);
            this.messageValue.set(this.textareaRef().value);
            this.clearSearch();
            const allMentions = JSON.parse(this.props.record.data.social_post_mentions || "{}");
            const currentMentions = allMentions[this.props.socialMediaType] || {};
            currentMentions[replacedValue] = this.extractMentionData(replacedValue, option);
            allMentions[this.props.socialMediaType] = currentMentions;
            await this.props.record.update({
                [this.props.name]: this.textareaRef().value,
                social_post_mentions: JSON.stringify(allMentions),
            });
            this.textareaRef()?.blur();
        }
    }

    /**
     * Insert an `@` and trigger the mention popup.
     */
    async onMentionClick() {
        const originalContent = this.textareaRef().value;
        const start = this.textareaRef().selectionStart;
        const end = this.textareaRef().selectionEnd;
        const left = originalContent.slice(0, start);
        const right = originalContent.slice(end, originalContent.length);
        this.textareaRef().value = left + " @ " + right;
        this.textareaRef().dispatchEvent(new InputEvent("input"));
        this.textareaRef().dispatchEvent(new KeyboardEvent("keydown"));
        this.textareaRef().focus();
        const newCursorPos = start + 2;
        this.textareaRef().setSelectionRange(newCursorPos, newCursorPos);
        this.onInputDetectMention();
    }

    extractMentionData(mentionedUserName, option) {
        return mentionedUserName;
    }

    /**
     * Return the remaining chars count for all selected medias when we don't split.
     * Or for the current media if we split.
     */
    get remainingCharsPerMedia() {
        let maxPostLengthPerMedia = this.props.record.data.max_post_length_per_media || [];
        if (this.props.socialMediaType) {
            const medias = this.props.record.data.max_post_length_per_media || [];
            maxPostLengthPerMedia = medias.filter(
                ({ mediaType }) => mediaType === this.props.socialMediaType
            );
        }
        return maxPostLengthPerMedia.map(({ mediaId, mediaType, maxPostLength }) => ({
            mediaId,
            mediaType,
            remainingCount: maxPostLength - this.count(),
        }));
    }
}

export const socialPostMessageField = {
    ...emojisTextField,
    additionalClasses: [
        ...(emojisTextField.additionalClasses || []),
        "o_social_post_message_field",
    ],
    extractProps({ attrs }) {
        const props = emojisTextField.extractProps(...arguments);
        props.socialMediaType = attrs.social_media;
        props.placeholder = _t("What do you want to say?");
        return props;
    },
    component: SocialPostMessageField,
};

registry.category("fields").add("social_post_message_field", socialPostMessageField);
