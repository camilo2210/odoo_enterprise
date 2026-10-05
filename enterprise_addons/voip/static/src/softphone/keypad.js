import { useLayoutEffect } from "@web/owl2/utils";
import { useSelection } from "@mail/utils/common/hooks";
import { Component, markup, useEffect, useProps, proxy, signal, t, untrack } from "@odoo/owl";
import { useLongPress } from "@voip/hooks/long_press_hook";
import { ActionButton } from "@voip/softphone/action_button";
import { AddressBook, PRIORITIZED_CONTACT_LIMIT } from "@voip/softphone/address_book";
import {
    getSortedMatchingContacts,
    makeContactComparator,
    prioritizeContactsByIds,
} from "@voip/utils/contact_search";
import { CountrySelectorItems } from "@voip/softphone/country_selector_items";
import { KeypadModel } from "@voip/softphone/keypad_model";
import { highlightT9Name, isT9Code } from "@voip/softphone/t9";
import { highlightMatch, highlightPhone } from "@voip/utils/highlight";
import { VoipImStatus } from "@voip/softphone/voip_im_status";
import { isCurrentFocusEditable } from "@voip/utils/utils";
import { cleanPhoneNumber } from "@web/core/phone/phone_call";
import { isBrowserFirefox } from "@web/core/browser/feature_detection";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

const MAX_EXACT_OTHER_CONTACTS = 30;
const KEYPAD_CONTACT_FETCH_LIMIT = MAX_EXACT_OTHER_CONTACTS + 2;

/**
 * The actual keypad, its search bar, and recipient suggestions.
 */
export class Keypad extends Component {
    static components = {
        ActionButton,
        AddressBook,
        CountrySelectorItems,
        Dropdown,
        VoipImStatus,
    };
    props = useProps({
        dtmf: t.boolean().optional(false),
        onCallVoicemail: t.function().optional(),
        onClickBack: t.function().optional(),
        onClickContact: t.function().optional(),
        onClickHistory: t.function().optional(),
        onSubmit: t.function().optional(),
        state: t.instanceOf(KeypadModel),
        slots: t.object().optional(),
    });
    static template = "voip.Keypad";

    keypadRootRef = signal.ref();
    inputRef = signal.ref();
    firstSuggestionButtonRef = signal.ref();

    setup() {
        this.voip = useService("voip");
        this.userAgent = this.voip.userAgent;
        this.softphone = this.voip.softphone;
        this.state = proxy(this.props.state);
        this.compareContacts = makeContactComparator(user.lang);
        this.prioritizedContactIdsBySearchTerms = new Map();
        this.prioritizedContacts = proxy({ searchTerms: "", contactIds: [] });
        this.countryMenuRef = signal.ref();
        this.selection = useSelection({
            ref: this.inputRef,
            model: this.props.state.input.selection,
            preserveOnClickAwayPredicate: (ev) => this.keypadRootRef()?.contains(ev.target),
        });
        useLayoutEffect(
            (shouldFocusInput) => {
                if (
                    shouldFocusInput &&
                    this.inputRef() &&
                    !this.voip.error &&
                    (document.activeElement === this.inputRef() || !isCurrentFocusEditable())
                ) {
                    // By default, the <input> is rendered with "none" as
                    // inputMode, which should ensure that no update from OWL
                    // would open the keyboard. We also re-force "none" here, in
                    // the function that controls the focus. We only set to
                    // "text" when the user actually engages with the input
                    // using his finger. As soon as the input will change in any
                    // other way than using the mobile keyboard, this will be
                    // switched back to "none".
                    this.inputRef().inputMode = "none";

                    // This is important to restore, blur and focus in that
                    // order here, this is what allows the cursor to be placed
                    // at the right position AND the input scrolled accordingly,
                    // especially when the input is full.
                    // Notice that this does not simulate the exact same thing
                    // as typing with a real keyboard though:
                    // - If the cursor is at the end, this is the same.
                    // - If the cursor is at the start, this is the same.
                    // - If the cursor is in the middle, and the scroll is not
                    //   at the start, the cursor stays visually in position as
                    //   more characters are added, instead of pushing existing
                    //   characters to the right. This is judged acceptable
                    //   (also this is only the case on Chrome).
                    // See KEYPAD_CURSOR.
                    this.selection.restore();
                    this.inputRef().blur();
                    this.inputRef().focus();

                    this.props.state.input.focus = false;
                }
            },
            () => [this.props.state.input.focus, this.props.state.showMore]
        );
        this.onInputSearchBarDebounced = useDebounced((ev) => {
            this.onInputSearchBar(ev);
        }, 300);
        const keypad = this;
        this.addressBookState = {
            get searchInputValue() {
                return keypad.props.state.input.value;
            },
            set searchInputValue(value) {
                keypad.props.state.input.value = value;
            },
            prioritizedContactIdsBySearchTerms: this.prioritizedContactIdsBySearchTerms,
        };
        let isFirstRender = true;
        useEffect(() => {
            const prefillContext = this.state.prefillContext;
            if (isFirstRender) {
                untrack(() => this.setUpInitCountry());
            } else if (prefillContext) {
                untrack(() => this.parsePhoneNumber());
            }
            isFirstRender = false;
        });

        this.longPressHandler = useLongPress(this.onLongPress.bind(this));
    }

    onCountryDropdownStateChanged(isOpen) {
        this.props.state.input.focus = !isOpen;
        if (isOpen) {
            // Note that `useAutofocus` is not compatible with the softphone
            // being the active element. It also would not work on mobile
            // anyway. It is better to follow dropdown state changes and handle
            // it here in the end, if not adding new generic dropdown options
            // in the framework.
            this.countryMenuRef()?.querySelector("input")?.focus();
        }
    }

    get keys() {
        return [
            { key: "1", longPressAction: this.showVoicemailIcon ? "voicemail" : null },
            { key: "2", letters: "ABC" },
            { key: "3", letters: "DEF" },
            { key: "4", letters: "GHI" },
            { key: "5", letters: "JKL" },
            { key: "6", letters: "MNO" },
            { key: "7", letters: "PQRS" },
            { key: "8", letters: "TUV" },
            { key: "9", letters: "WXYZ" },
            { key: "*", letters: "", icon: "emergency" },
            { key: "0", letters: "+", longPress: "+" },
            { key: "#", letters: "", icon: "tag" },
        ];
    }

    get calleeSuggestions() {
        const searchTerms = this.props.state.input.value.trim();
        if (!searchTerms) {
            return { length: 0 };
        }
        let contacts = getSortedMatchingContacts(
            this.voip.softphone.contacts,
            searchTerms,
            this.compareContacts
        );
        if (!this.isTransferKeypad) {
            const prioritizedContactIds =
                this.prioritizedContacts.searchTerms === searchTerms
                    ? this.prioritizedContacts.contactIds
                    : this.prioritizedContactIdsBySearchTerms.get(searchTerms);
            if (prioritizedContactIds?.length) {
                contacts = prioritizeContactsByIds(contacts, prioritizedContactIds);
            }
        }
        return {
            length: contacts.length,
            firstResult: contacts[0] ? this.getCalleeSuggestion(contacts[0], searchTerms) : null,
        };
    }

    getCalleeSuggestion(contact, searchTerms) {
        return {
            contact,
            name:
                (isT9Code(searchTerms) &&
                    highlightT9Name(contact.voipName, contact.t9_name, searchTerms)) ||
                highlightMatch(contact.voipName, searchTerms) ||
                highlightMatch(contact.complete_name || "", searchTerms) ||
                contact.voipName,
            phone:
                highlightPhone(contact.phone, searchTerms) ||
                highlightPhone(contact.phone_formatted || "", searchTerms) ||
                contact.phone,
        };
    }

    get country() {
        return this.props.state.input.country;
    }

    /** @returns {ReturnType<markup>} */
    get firstSuggestion() {
        const suggestion = this.calleeSuggestions.firstResult;
        return markup`${suggestion.name} <span class="ms-2">${suggestion.phone}</span>`;
    }

    get firstSuggestionTooltipText() {
        return this.calleeSuggestions.firstResult?.contact?.complete_name;
    }

    get flagAltLabel() {
        if (!this.country) {
            return "";
        }
        return _t("%(country)s (+%(phone_prefix)s)", {
            country: this.country.code,
            phone_prefix: this.country.phone_code,
        });
    }

    get showOthersButtonText() {
        const numberOfOthers = this.calleeSuggestions.length - 1;
        switch (numberOfOthers) {
            case -1:
            case 0:
                return "";
            case 1:
                return _t("1 other…");
            case 2:
                return _t("2 others…");
            default:
                return numberOfOthers > MAX_EXACT_OTHER_CONTACTS
                    ? _t("%s+ others…", numberOfOthers - 1)
                    : _t("%s others…", numberOfOthers);
        }
    }

    get showVoicemailIcon() {
        return Boolean(this.voip.config.voicemailCode && this.props.onCallVoicemail);
    }

    get isTransferKeypad() {
        return (
            this.softphone.inCallView.activeView === "transfer" &&
            this.softphone.inCallView.transferView.activeView === "keypad"
        );
    }

    async getLastCall() {
        const ids = await this.voip.fetchRecentCalls({ limit: 1 });
        if (!ids) {
            return null;
        }
        return this.voip.store["voip.call"].get(ids[0]);
    }

    focusInputAtEnd() {
        this.selection.moveCursor(this.props.state.input.value.length);
        this.props.state.input.focus = true;
    }

    onClickBack() {
        if (this.props.state.showMore) {
            this.props.state.showMore = false;
            this.focusInputAtEnd();
        } else if (this.props.onClickBack) {
            this.props.onClickBack();
        }
    }

    doBackspace(isLongPress) {
        const { selectionStart, selectionEnd } = this.inputSelection;
        const value = this.props.state.input.value;
        let cursorPosition, newValue;
        if (isLongPress) {
            // Wherever the cursor is and how many characters are selected, long
            // press on the backspace button means "clear the keypad input",
            // just like in the keypad on smartphones phone apps.
            cursorPosition = 0;
            newValue = "";
        } else {
            cursorPosition =
                selectionStart === selectionEnd && selectionStart !== 0
                    ? selectionStart - 1
                    : selectionStart;
            newValue =
                selectionEnd !== 0
                    ? value.slice(0, cursorPosition) + value.slice(selectionEnd)
                    : undefined;
        }
        this.voip.invalidatePrefill();
        if (newValue !== undefined) {
            this.props.state.input.value = newValue;
            this.parsePhoneNumber();
        }
        this.selection.moveCursor(cursorPosition);
        this.props.state.input.focus = true;
        this.onInputSearchBar();
    }

    onClickBackspace() {
        if (!this.longPressHandler.longPressTriggered) {
            this.doBackspace(false);
        }
    }

    onClickContact(contact) {
        this.props.onClickContact(contact);
    }

    async onCountrySelected(country) {
        this.voip.invalidatePrefill();
        const prefillInputSeq = this.voip._prefillInputSeq;
        const data = await rpc("/voip/update_country_code", {
            data: {
                phone_number: this.props.state.input.value,
                iso: this.props.state.input.country?.code,
                itu: this.props.state.input.country?.phone_code,
            },
            target_country_data: {
                iso: country.code,
                itu: country.phone_code,
            },
        });
        if (prefillInputSeq !== this.voip._prefillInputSeq) {
            return;
        }
        this.props.state.input.country = country;
        this.props.state.input.value = data.phone_number;
        this.props.state.input.isValid = data.isValid;
        this.selection.moveCursor(data.phone_number.length);
    }

    onPointerDown(ev, key) {
        if (ev.button !== 0) {
            return;
        }
        // Prevent losing the focus on the input when using the keypad,
        // otherwise the focus style would flicker on each click. This is also
        // needed to ensure proper behavior of the cursor when using the keypad
        // with a full input (see KEYPAD_CURSOR).
        ev.preventDefault();
        if (key) {
            return this.longPressHandler.onPointerDown(ev, key);
        }
    }

    onLongPress(key) {
        if (key === "KEYPAD_BACKSPACE") {
            this.doBackspace(true);
        } else if (key.longPressAction === "voicemail") {
            this.props.onCallVoicemail();
        } else {
            this.onClickKey(key.longPress ? key.longPress : key.key);
        }
    }

    onKeypadClick(ev, key) {
        if (!this.longPressHandler.longPressTriggered) {
            this.onClickKey(key.key);
        }
    }

    /** @param {string} key */
    onClickKey(key) {
        if (this.props.dtmf) {
            this.userAgent.frontSession.sendDtmf(key);
            this.props.state.input.value += key;
        } else {
            const { selectionStart, selectionEnd } = this.inputSelection;
            const value = this.props.state.input.value;
            this.props.state.input.value =
                value.slice(0, selectionStart) + key + value.slice(selectionEnd);

            // Forcing the input value immediately here prevents a visual glitch
            // on Firefox: when the input is full, cursor at the end and that a
            // keypad button is clicked, the number is added at the right place
            // and the cursor is effectively moved at the end but visually, it
            // is not moved immediately over there. TODO find a better way.
            if (isBrowserFirefox()) {
                this.inputRef().value = this.props.state.input.value;
            }

            this.selection.moveCursor(selectionStart + 1);
            this.props.state.input.focus = true;
            this.onInputSearchBar();
        }
        this.voip.invalidatePrefill();
    }

    onClickShowMore() {
        this.props.state.showMore = true;
        this.focusInputAtEnd();
    }

    /**
     * Asynchronously initializes the country code when setup.
     *
     * Priority: parsed input → last call's country → active company's country.
     *
     * @returns {Promise<void>}
     */
    async setUpInitCountry() {
        const prefillInputSeq = this.voip._prefillInputSeq;
        const hadInput = Boolean(this.props.state.input.value);
        if (hadInput) {
            await this.parsePhoneNumber();
            if (prefillInputSeq !== this.voip._prefillInputSeq || this.props.state.input.country) {
                return;
            }
        }
        const lastCall = await this.getLastCall();
        if (
            (hadInput && prefillInputSeq !== this.voip._prefillInputSeq) ||
            (!hadInput && this.props.state.prefillContext)
        ) {
            return;
        }
        this.props.state.input.country =
            lastCall?.country_id ||
            this.voip.store["res.country"].get(user.activeCompany.country_id) ||
            null;
    }

    syncSelectionWithInput() {
        // On Android, the input is blurred when the native keyboard closes,
        // so we need to keep the model’s state aligned with the element’s selection.
        const element = this.inputRef();
        Object.assign(this.props.state.input.selection, {
            start: element.selectionStart ?? 0,
            end: element.selectionEnd ?? 0,
            direction: element.selectionDirection ?? "none",
        });
    }

    onInput(ev) {
        this.syncSelectionWithInput();
        this.voip.invalidatePrefill();
        this.parsePhoneNumber();
        this.onInputSearchBarDebounced(ev);
    }

    async onInputSearchBar(ev) {
        const searchTerms = this.props.state.input.value.trim();
        if (!searchTerms || this.props.state.showMore) {
            return;
        }
        this.prioritizedContacts.searchTerms = searchTerms;
        this.prioritizedContacts.contactIds =
            this.prioritizedContactIdsBySearchTerms.get(searchTerms) || [];
        const prioritizedContactIds = await this.voip.fetchContacts({
            searchTerms,
            limit: KEYPAD_CONTACT_FETCH_LIMIT,
            prioritizedContactsLimit: this.isTransferKeypad ? 0 : PRIORITIZED_CONTACT_LIMIT,
        });
        if (this.props.state.input.value.trim() === searchTerms) {
            this.prioritizedContactIdsBySearchTerms.set(searchTerms, prioritizedContactIds);
            this.prioritizedContacts.contactIds = prioritizedContactIds;
        }
    }

    /** @param {KeyboardEvent} ev */
    onSearchInputKeydown(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }

        if (ev.key === "Enter") {
            const inputValue = this.props.state.input.value.trim();
            if (!inputValue) {
                return;
            }
            this.props.onSubmit?.();
        } else if (ev.key === "ArrowDown") {
            if (!this.firstSuggestionButtonRef()) {
                return;
            }
            // If not at the end of the input, let the ArrowDown key have its
            // default effect of going to the end of the input.
            const { value: text, selectionStart, selectionEnd } = ev.currentTarget;
            if (selectionStart === text.length && selectionEnd === text.length) {
                // End of input -> Suggestion
                ev.preventDefault();
                this.firstSuggestionButtonRef().focus();
            }
        }
    }

    /** @param {KeyboardEvent} ev */
    onSuggestionKeydown(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }
        if (ev.key === "ArrowDown") {
            if (ev.currentTarget.nextElementSibling) {
                // Suggestion -> Show more
                ev.preventDefault();
                ev.currentTarget.nextElementSibling.focus();
            }
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            if (ev.currentTarget.previousElementSibling) {
                // Show more -> Suggestion
                ev.currentTarget.previousElementSibling.focus();
            } else {
                // Suggestion -> Input
                this.inputRef().focus();
            }
        }
    }

    async parsePhoneNumber() {
        const prefillInputSeq = this.voip._prefillInputSeq;
        if (this._parsePhoneNumberRpc) {
            this._parsePhoneNumberRpc.abort();
        }

        const phoneNumber = this.props.state.input.value;
        const invalidPattern = /[^\d+\- ()./]/;
        if (invalidPattern.test(phoneNumber)) {
            return;
        }

        const currentRpc = rpc("/voip/parse_phone_number", {
            data: {
                phone_number: phoneNumber,
                iso: this.props.state.input.country?.code,
                itu: this.props.state.input.country?.phone_code,
            },
        });
        this._parsePhoneNumberRpc = currentRpc;

        try {
            var data = await currentRpc;
        } catch (error) {
            if (error.event?.type === "abort") {
                error.event.preventDefault();
                return;
            }
            if (error.message?.toLowerCase().includes("abort")) {
                return;
            }
            console.error(error);
            return;
        } finally {
            if (this._parsePhoneNumberRpc === currentRpc) {
                this._parsePhoneNumberRpc = null;
            }
        }

        if (prefillInputSeq !== this.voip._prefillInputSeq) {
            return;
        }

        if (this.props.state.input.isValid && !data.isValid) {
            data.phone_number = cleanPhoneNumber(data.phone_number);
        }
        this.props.state.input.value = data.phone_number;
        if (!this.props.state.input.isValid && data.isValid) {
            this.selection.moveCursor(data.phone_number.length);
        }
        this.props.state.input.isValid = data.isValid;
        this.voip.store.insert(data.storeData);
        this.props.state.input.country = this.voip.store["res.country"].get(data.countryId) || null;
    }

    get inputSelection() {
        return {
            selectionStart: this.props.state.input.selection.start,
            selectionEnd: this.props.state.input.selection.end,
        };
    }
}
