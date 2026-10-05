/**
 * A list of field widget keys of the wowl's field registry (`registry.category("fields")`)
 * that are safe for the user to swith to when editing a field's properties in the view editor's sidebar.
 *
 * Other widgets either don't make sense for that use because they are too specific, or they need
 * specific implementation details provided by some view to be usable.
 */
export const SIDEBAR_SAFE_FIELDS = [
    "badge",
    "badges_selection",
    "badges_many2one",
    "handle",
    "percentpie",
    "radio",
    "selection",
    "image_url",
    "ace",
    "priority",
    "date",
    "datetime",
    "relative_date",
    "email",
    "phone",
    "url",
    "binary",
    "image",
    "pdf_viewer",
    "boolean",
    "state_selection",
    "boolean_toggle",
    "statusbar",
    "float",
    "float_time",
    "integer",
    "monetary",
    "percentage",
    "progressbar",
    "text",
    "boolean_favorite",
    "boolean_icon",
    "char",
    "statinfo",
    "html",
    "text_emojis",
    "CopyClipboardChar",
    "CopyClipboardURL",
    "char_emojis",
    "many2many_tags",
    "many2many_tags_color_dot",
    "many2one",
    "many2many",
    "one2many",
    "sms_widget",
    "reference",
    "daterange",
    "google_address_autocomplete",
];

/**
 * Lists of blacklisted widget types organised per view type.
 * Certain widgets such as the form status bar widget are designed to be used on single records.
 * While, it is technically possible to use these widgets on record set views such as the list view, this leads to massive performance issues even for basic selection fields.
 */
export const SIDEBAR_VIEW_DEPENDENT_BLACKLIST = {
    form: ["badge", "statusbar"],
    list: ["badge", "statusbar"],
};
