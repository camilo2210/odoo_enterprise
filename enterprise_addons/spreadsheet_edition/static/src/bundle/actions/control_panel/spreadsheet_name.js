import { UNTITLED_SPREADSHEET_NAME } from "@spreadsheet/helpers/constants";

import { computed, Component, onMounted, useProps, proxy, signal, t, useEffect } from "@odoo/owl";

const WIDTH_MARGIN = 3;
const PADDING_RIGHT = 5;
const PADDING_LEFT = PADDING_RIGHT - WIDTH_MARGIN;

export class SpreadsheetName extends Component {
    static template = "spreadsheet_edition.SpreadsheetName";
    props = useProps({
        name: t.string(),
        isReadonly: t.boolean(),
        onSpreadsheetNameChanged: t.function().optional(() => () => {}),
    });

    speadsheetNameInputRef = signal.ref();

    setup() {
        this.placeholder = UNTITLED_SPREADSHEET_NAME;
        this.state = proxy({
            name: this.props.name,
            inputSize: 1,
        });

        onMounted(() => {
            this._setInputSize(this.state.name);
        });
        this.isUntitled = computed(() => this._isUntitled(this.state.name));
        useEffect(() => {
            this.state.name = this.props.name;
        });
    }

    /**
     * @private
     * @param {string} text in the input element
     */
    _setInputSize(text) {
        const { fontFamily, fontSize } = window.getComputedStyle(this.speadsheetNameInputRef());
        const font = `${fontSize} ${fontFamily}`;
        this.state.inputSize =
            this._computeTextWidth(text || this.placeholder, font) + PADDING_RIGHT + PADDING_LEFT;
    }

    /**
     * Return the width in pixels of a text with the given font.
     * @private
     * @param {string} text
     * @param {string} font css font attribute value
     * @returns {number} width in pixels
     */
    _computeTextWidth(text, font) {
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        context.font = font;
        const width = context.measureText(text).width;
        // add a small extra margin, otherwise the text jitters in
        // the input because it overflows very slightly for some
        // letters (?).
        return Math.ceil(width) + WIDTH_MARGIN;
    }

    /**
     * Check if the name is empty or is the generic name
     * for untitled spreadsheets.
     * @param {string} name
     * @returns {boolean}
     */
    _isUntitled(name) {
        name = name.trim();
        return !name || name === this.placeholder.toString();
    }

    /**
     * @private
     * @param {InputEvent} ev
     */
    _onFocus(ev) {
        if (this._isUntitled(ev.target.value)) {
            this.state.name = this.placeholder;
            ev.target.value = this.placeholder;
            ev.target.select();
        }
    }

    /**
     * @private
     * @param {InputEvent} ev
     */
    _onInput(ev) {
        const value = ev.target.value;
        this.state.isUntitled = this._isUntitled(value);
        this.state.name = value;
        this._setInputSize(value);
    }

    /**
     * @private
     * @param {InputEvent} ev
     */
    _onNameChanged(ev) {
        const value = ev.target.value.trim();
        this.state.name = value || this.props.name;
        this._setInputSize(this.state.name);
        this.props.onSpreadsheetNameChanged({
            name: this.state.name,
        });
        ev.target.blur();
    }
}
