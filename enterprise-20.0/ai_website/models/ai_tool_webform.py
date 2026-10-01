# Part of Odoo. See LICENSE file for full copyright and licensing details.

import contextlib
import json
import re
import secrets

from lxml import etree, html as lxml_html

from odoo import api, models

from odoo.addons.ai_website.models.ai_website_service import _WHOLE_ZONE_SELECTORS

# The public form runtime re-injects a fresh signature on every render
# (website/tools.py add_form_signature), so any signature in generated or
# fetched markup is dead weight, and a hardcoded hash trips the safety
# reviewer. Strip them everywhere.
_FORM_SIGNATURE_RE = re.compile(r'<input\b[^>]*website_form_signature[^>]*>\s*', re.IGNORECASE)

_SUCCESS_MODES = ('redirect', 'message', 'nothing')

# The field types the editor can render, one website.form_field_* template
# each (website_form_editor.xml). Any other data-type crashes the sidebar's
# field rendering.
_FIELD_TYPES = frozenset((
    'char', 'text', 'email', 'tel', 'url', 'integer', 'float', 'monetary',
    'date', 'datetime', 'binary', 'boolean', 'selection', 'many2one',
    'one2many', 'many2many', 'html',
))

_EMAIL_TO_INPUT_RE = re.compile(r'<input\b[^>]*\bname="email_to"[^>]*>', re.IGNORECASE)

# The accept values the editor's file-type options produce. The submit
# validator matches them against the files' MIME types, so anything else
# (e.g. an extension list) rejects every upload.
_FILE_ACCEPT_VALUES = frozenset((
    'image/*', 'application/pdf', 'application/*', 'video/*', 'audio/*',
))


def _blank_email_to_values(html):
    """Clear the `value` attribute of any `email_to` inputs in the HTML.
    This prevents the AI from silently copying the default company address
    from snippets without the user's explicit approval."""
    return _EMAIL_TO_INPUT_RE.sub(
        lambda match: re.sub(r'\bvalue="[^"]*"', 'value=""', match.group(0)),
        html,
    )


def _with_class(cls):
    """Generate an XPath condition to safely match a class name within a
    space-separated class attribute."""
    return f'contains(concat(" ", normalize-space(@class), " "), " {cls} ")'


def _field_name(field_el):
    """The name a field wrapper submits under. A multi-option field carries it
    on its group wrapper, every other field on its input."""
    return next(iter(field_el.xpath(
        f'.//*[{_with_class("s_website_form_multiple")}]/@data-name'
        f' | .//*[{_with_class("s_website_form_input")}]/@name')), None)


class AIToolWebform(models.AbstractModel):
    """Webform support for the website builder agent.

    The agent builds forms by writing HTML adapted from the canonical form
    snippets; this layer makes those forms functional by construction:

    - a normalizer gates every HTML apply: purely mechanical details
      (signatures, ids, submit anchor, custom-vs-bound markers) are repaired
      in place, while anything that would break the submission or the editor
      and needs the model's (or the user's) intent raises, so the error goes
      back through the tool result and the model corrects its own output;
    - the "Set Form Action" tool wires a form through the form editor's own
      client-side code paths, and the "Get Webform Info" tool describes the
      available form actions and their bindable fields.
    """
    _inherit = 'ai.tool'

    @api.model
    def _ai_tool_apply_html_to_page(self, tool_context, actions):
        """Normalize the webforms in the actions before the base apply
        pipeline runs."""
        # Some providers send structured arguments JSON-encoded; parse before
        # normalizing.
        if isinstance(actions, str):
            with contextlib.suppress(json.JSONDecodeError):
                actions = json.loads(actions)
        if isinstance(actions, list):
            # Before super(): the safety reviewer must never see a signature.
            self._normalize_webform_actions(actions)
        return super()._ai_tool_apply_html_to_page(tool_context, actions)

    @api.model
    def _ai_tool_get_snippets(self, snippet_keys):
        """Strip live signatures and blank out email recipients from fetched
        snippets to prevent the model from faithfully copying them."""
        result = super()._ai_tool_get_snippets(snippet_keys)
        if isinstance(result, str):
            result = _FORM_SIGNATURE_RE.sub('', result)
            result = _blank_email_to_values(result)
        return result

    @api.model
    def _normalize_webform_actions(self, actions):
        """Validate and normalize the webforms of every action's content,
        in place."""
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            content = action.get('content') or ''
            if 's_website_form' not in content and '<form' not in content:
                continue
            content = _FORM_SIGNATURE_RE.sub('', content)
            try:
                root = lxml_html.fragment_fromstring(content, create_parent='div')
            except (etree.ParserError, ValueError):
                # Unparseable content is the sanitizer's problem, not ours.
                action['content'] = content
                continue
            # The palette only ever nests the form section inside a wrapper
            # snippet section, so a page-level one is always wrong; only a
            # targeted replace may hold one as fragment root, to swap the
            # existing nested form section in place.
            selector = (action.get('selector') or '').strip().lower()
            if (action.get('mode') in ('before', 'after') or not selector
                    or selector in _WHOLE_ZONE_SELECTORS.get(action.get('zone'), ())):
                if any('s_website_form' in child.classes for child in root):
                    raise ValueError(
                        f"Action #{index}: a section carrying s_website_form cannot sit "
                        "directly at page level; it is always nested inside a wrapper "
                        "section, as in the droppable form snippets (s_title_form, "
                        "s_form_aside, s_website_form_cover). Fetch one and keep its "
                        "structure."
                    )
            self._normalize_webforms(index, root)
            action['content'] = (root.text or '') + ''.join(
                lxml_html.tostring(child, encoding='unicode') for child in root)

    @api.model
    def _normalize_webforms(self, index, root):
        """Normalize every webform of the fragment, after the fragment-wide
        checks: no form field outside a <form>, and a non-empty end message
        for every form whose success mode shows one."""
        if root.xpath(f'//*[({_with_class("s_website_form_field")} or {_with_class("s_website_form_input")}) and not(ancestor::form)]'):
            raise ValueError(
                f"Action #{index}: the HTML contains form fields outside of a <form> "
                "element; they can never be submitted. Fetch a form snippet with "
                "\"Get Snippets\" and keep the fields inside its <form>."
            )
        fields_by_model = {}
        actions_by_key = self._get_webform_actions()
        for form in root.xpath('//form'):
            is_webform = form.get('data-model_name') or form.xpath(f'.//*[{_with_class("s_website_form_input")}]')
            if not is_webform:
                continue  # e.g. a search bar
            self._normalize_webform(index, form, actions_by_key, fields_by_model)
            if form.get('data-success-mode') == 'message':
                # The runtime looks the message up with
                # `form.parentNode.querySelector`, so anywhere else is invisible.
                message = form.getparent().xpath(f'.//*[{_with_class("s_website_form_end_message")}]')
                if not message or (len(message[0]) == 0 and not (message[0].text or '').strip()):
                    raise ValueError(
                        f"Action #{index}: the form uses data-success-mode=\"message\" but "
                        "the div.s_website_form_end_message to show after submission is "
                        "missing or empty. Include it, with real themed content, as a "
                        "SIBLING right after the form in the SAME action (widen the "
                        "selector if it already exists on the page outside the replaced "
                        "element)."
                    )

    @api.model
    def _normalize_webform(self, index, form, actions_by_key, fields_by_model):
        """Normalize one webform: check its action wiring, structure and
        fields, repairing what is purely mechanical and raising whenever the
        model must rewrite its HTML."""
        model = form.get('data-model_name')
        if not model:
            raise ValueError(
                f"Action #{index}: the form has fields but no data-model_name, so "
                "submissions go nowhere. Wire the form to an action with the "
                "\"Set Form Action\" tool."
            )
        if model not in {a['model'] for a in actions_by_key.values()}:
            raise ValueError(
                f"Action #{index}: the form targets the model '{model}' which is not "
                "enabled for website forms. Use the \"Get Webform Info\" tool to list "
                "the available form actions and their models."
            )
        if model not in fields_by_model:
            fields_by_model[model] = self.env['ir.model'].get_authorized_fields(model, {})
        authorized_fields = fields_by_model[model]

        rows = form.xpath(f'.//*[{_with_class("s_website_form_rows")}]')
        submit = form.xpath(f'.//*[{_with_class("s_website_form_submit")}]')
        if not rows or not submit:
            raise ValueError(
                f"Action #{index}: the form structure is incomplete (missing the "
                "s_website_form_rows container or the s_website_form_submit block). "
                "Fetch a form snippet with \"Get Snippets\" and keep its structure."
            )
        if not submit[0].xpath(f'.//*[{_with_class("s_website_form_send")}]'):
            raise ValueError(
                f"Action #{index}: the form has no submit button "
                "(a.s_website_form_send inside the s_website_form_submit block)."
            )
        # The runtime renders the submission status after this span; without it
        # every submit crashes in the visitor's browser.
        if not submit[0].xpath('.//span[@id="s_website_form_result"]'):
            span = etree.SubElement(submit[0], 'span')
            span.set('id', 's_website_form_result')
            send = submit[0].xpath(f'.//*[{_with_class("s_website_form_send")}]')[0]
            send.addprevious(span)

        if form.xpath('.//input[not(normalize-space(@name))] | .//select[not(normalize-space(@name))] | .//textarea[not(normalize-space(@name))]'):
            raise ValueError(
                f"Action #{index}: the form contains an input without a name; its "
                "value would be lost on submission. Name every input."
            )

        invalid_types = {
            field_type
            for field_type in form.xpath(f'.//*[{_with_class("s_website_form_field")}]/@data-type')
            if field_type not in _FIELD_TYPES
        }
        if invalid_types:
            raise ValueError(
                f"Action #{index}: invalid field data-type(s) "
                f"{', '.join(sorted(invalid_types))} - the editor breaks on them. "
                "data-type is the ORM field type, never the HTML input type "
                f"(a numeric field is integer or float). Valid values: "
                f"{', '.join(sorted(_FIELD_TYPES))}."
            )

        # One field without its structural label breaks the editing sidebar
        # for the whole form.
        if form.xpath(f'.//*[{_with_class("s_website_form_field")}'
                      f' and not({_with_class("s_website_form_dnone")})'
                      f' and not(.//label[{_with_class("s_website_form_label")}])]'):
            raise ValueError(
                f"Action #{index}: a field is missing its <label "
                "class=\"s_website_form_label\">; every field wrapper must contain "
                "one, single checkboxes included (their caption goes IN that label; "
                "the form-check div holds only the input). Without it the field "
                "cannot be edited."
            )

        # A native temporal input bypasses the date wrapper the runtime
        # serializes from.
        if form.xpath('.//input[@type="date" or @type="datetime-local" or @type="time"]'):
            raise ValueError(
                f"Action #{index}: never use native date inputs (type=\"date\", "
                "\"datetime-local\" or \"time\"), their raw value makes every "
                "submission crash. A date/datetime field is a text input with class "
                "\"datetimepicker-input s_website_form_input\" inside a "
                "div.s_website_form_date (or _datetime) with classes "
                "\"input-group date\"."
            )
        for field in form.xpath(f'.//*[{_with_class("s_website_form_field")}]'
                                '[@data-type="date" or @data-type="datetime"]'):
            if not field.xpath(f'.//*[{_with_class("s_website_form_date")} or {_with_class("s_website_form_datetime")}]'):
                raise ValueError(
                    f"Action #{index}: a date/datetime field is missing its picker "
                    "wrapper: put the text input (class \"datetimepicker-input "
                    "s_website_form_input\") inside a div.s_website_form_date (or "
                    "_datetime) with classes \"input-group date\", or its value "
                    "crashes the submission."
                )

        self._normalize_file_inputs(index, form)
        self._reconcile_field_names(index, form, authorized_fields)
        self._check_bound_choice_values(index, form, authorized_fields)
        self._check_required_fields(index, form, model)
        if model == 'mail.mail':
            self._ensure_email_to(form)
        self._normalize_field_ids(form)
        self._normalize_success_attrs(form)

    @api.model
    def _normalize_file_inputs(self, index, form):
        """Bounce accept values the submit validator cannot match, and stamp
        default file count/size limits when missing or zero."""
        for input_el in form.xpath(f'.//input[@type="file"][{_with_class("s_website_form_input")}]'):
            accept = (input_el.get('accept') or '').strip()
            if accept:
                invalid = [value for value in map(str.strip, accept.split(','))
                           if value not in _FILE_ACCEPT_VALUES]
                if invalid:
                    raise ValueError(
                        f"Action #{index}: the file field's accept value(s) "
                        f"{', '.join(invalid)} reject every upload. accept takes only: "
                        f"{', '.join(sorted(_FILE_ACCEPT_VALUES))} (comma-separated), "
                        "or omit it to allow any file."
                    )
            for attr, default in (('data-max-files-number', '1'), ('data-max-file-size', '64')):
                value = input_el.get(attr) or ''
                if not value.isdigit() or int(value) == 0:
                    input_el.set(attr, default)
            if int(input_el.get('data-max-files-number')) > 1:
                input_el.set('multiple', '')

    @api.model
    def _reconcile_field_names(self, index, form, authorized_fields):
        """Make each field's custom-field marker match its input name, and
        validate hidden presets.

        A field bound to a model field must not carry the marker (the editor
        renames a custom field's input after its label, dropping the binding);
        an unknown name must carry it (unmarked, the name is sent to the
        whitelist RPC at save, which rejects it). A hidden relational preset
        must hold a numeric record id."""
        for field in form.xpath(f'.//*[{_with_class("s_website_form_field")}]'):
            if 's_website_form_dnone' in field.classes:
                continue
            name = _field_name(field)
            if not name:
                continue
            classes = (field.get('class') or '').split()
            is_bound = name in authorized_fields and not authorized_fields[name].get('_property')
            if is_bound and 's_website_form_custom' in classes:
                classes.remove('s_website_form_custom')
                field.set('class', ' '.join(classes))
            elif not is_bound and 's_website_form_custom' not in classes:
                classes.append('s_website_form_custom')
                field.set('class', ' '.join(classes))
        for hidden in form.xpath(f'.//*[{_with_class("s_website_form_dnone")}]//input[@type="hidden"]'):
            name = hidden.get('name')
            field = authorized_fields.get(name)
            if field and not field.get('_property') and field.get('type') in ('many2one', 'integer'):
                value = hidden.get('value') or ''
                if not value.isdigit():
                    raise ValueError(
                        f"Action #{index}: the hidden field '{name}' must hold the "
                        "numeric id of the targeted record (look it up with the "
                        f"retrieval tools), not '{value}'."
                    )

    @api.model
    def _check_bound_choice_values(self, index, form, authorized_fields):
        """A choice input bound to a model field posts its option `value`
        verbatim, so anything but the field's selection key (or the record
        id) makes the insert raise and the visitor's submit die silently."""
        for field_el in form.xpath(f'.//*[{_with_class("s_website_form_field")}'
                                   f' and not({_with_class("s_website_form_dnone")})]'):
            name = _field_name(field_el)
            field = name and authorized_fields.get(name)
            if not field or field.get('_property'):
                continue
            # The empty entry is the editor's own "allow empty" option.
            values = [value for value in field_el.xpath(
                './/input[@type="radio"]/@value | .//input[@type="checkbox"]/@value'
                ' | .//select//option/@value') if value]
            if field.get('type') == 'selection':
                keys = {str(key) for key, _label in (field.get('selection') or [])}
                if any(value not in keys for value in values):
                    pairs = ', '.join(f"'{key}' = {label}" for key, label in (field.get('selection') or []))
                    raise ValueError(
                        f"Action #{index}: the options of the field '{name}' must have "
                        f"one of the model's selection keys as `value` ({pairs}), the "
                        "visible option text is free, the `value` is not. Other values "
                        "make every submission fail."
                    )
            elif field.get('type') in ('many2one', 'one2many', 'many2many'):
                if any(not value.isdigit() for value in values):
                    raise ValueError(
                        f"Action #{index}: the options of the relational field '{name}' "
                        "must have the targeted record's numeric id as `value` (look the "
                        "ids up with the retrieval tools), the visible option text is "
                        "free. Other values make every submission fail."
                    )

    @api.model
    def _check_required_fields(self, index, form, model):
        """Bounce when a required field of the target model has no input.

        Only form-writable fields are demanded: a required field that is
        blacklisted for website forms is the server's to fill (e.g. through a
        `website_form_input_filter` hook), never the form's."""
        names = set(form.xpath('.//input/@name | .//select/@name | .//textarea/@name'))
        writable_fields = self.env['ir.model']._get(model)._get_form_writable_fields({})
        missing = [
            name for name, field in writable_fields.items()
            if field.get('required') and not field.get('_property') and name not in names
        ]
        if missing:
            raise ValueError(
                f"Action #{index}: the form targets '{model}' but is missing the "
                f"mandatory field(s) {', '.join(missing)} - submissions would fail. "
                "Add them as visible fields (or hidden preset fields with a value)."
            )

    @api.model
    def _ensure_email_to(self, form):
        """Add the hidden email_to field back when the model dropped it. Without
        it the form renders with no website_form_signature and the server
        refuses every submission."""
        if form.xpath('.//input[@name="email_to"]'):
            return
        rows = form.xpath(f'.//*[{_with_class("s_website_form_rows")}]')[0]
        rows.insert(0, lxml_html.fragment_fromstring(
            '<div data-name="Field" class="s_website_form_field s_website_form_dnone">'
            '<input type="hidden" class="form-control s_website_form_input" name="email_to" value=""/>'
            '</div>'))

    @api.model
    def _normalize_field_ids(self, form):
        """Regenerate every field input id (and its label's `for`). The model
        copies snippet markup verbatim, so without this two forms on a page
        share ids and labels focus the wrong input."""
        for field in form.xpath(f'.//*[{_with_class("s_website_form_field")}]'):
            inputs = field.xpath(f'.//*[{_with_class("s_website_form_input")}]')
            if not inputs:
                continue
            base_id = 'o' + secrets.token_hex(6)  # like the editor's generateHTMLId()
            multiple = len(inputs) > 1
            old_to_new = {}
            for i, input_el in enumerate(inputs):
                new_id = f'{base_id}{i}' if multiple else base_id
                if input_el.get('id'):
                    old_to_new[input_el.get('id')] = new_id
                input_el.set('id', new_id)
                # An unset fill-with sometimes ends up serialized as the
                # literal string "undefined"; drop it.
                if input_el.get('data-fill-with') == 'undefined':
                    del input_el.attrib['data-fill-with']
            for label in field.xpath('.//label[@for]'):
                if label.get('for') in old_to_new:
                    label.set('for', old_to_new[label.get('for')])

    @api.model
    def _normalize_success_attrs(self, form):
        """Fall back to a valid success mode, and give redirect forms (the
        default mode) a target page so submitting never dead-ends."""
        mode = form.get('data-success-mode')
        if mode not in _SUCCESS_MODES:
            mode = 'redirect'
            form.set('data-success-mode', mode)
        if mode == 'redirect' and not (form.get('data-success-page') or '').strip():
            form.set('data-success-page', '/contactus-thank-you')

    # ------------------------------------------------------------------
    # Webform tools
    # ------------------------------------------------------------------

    @api.model
    def _get_webform_actions(self):
        """Map action key -> form-enabled model info, as the builder's Action
        selector sees it."""
        return {
            (model['website_form_key'] or model['model']): model
            for model in self.env['ir.model'].get_compatible_form_models()
        }

    @api.model
    def _ai_tool_set_webform_action(self, action_key, form_selector, fields):
        """Validate the action key and delegate the wiring to the
        `website_set_form_action` client tool, which runs the form editor's
        own action-switch code on the page."""
        if isinstance(fields, str):
            with contextlib.suppress(json.JSONDecodeError):
                fields = json.loads(fields)
        actions = self._get_webform_actions()
        if action_key not in actions:
            return f"Unknown form action '{action_key}'. Available actions: {', '.join(actions)}."
        return {"client_tool": {"name": "website_set_form_action", "params": {
            "selector": form_selector,
            "action_key": action_key,
            "fields": fields if isinstance(fields, list) else [],
        }}}

    @api.model
    def _ai_tool_get_webform_info(self, action_key):
        """Without an action key, list the available form actions; with one,
        describe it: its model and the fields available for binding."""
        actions = self._get_webform_actions()
        if not actions:
            return "No webform action is available on this database."
        if not action_key:
            result = (
                "The webform actions available on this database (the action decides what "
                "a submission creates):\n\n"
                "| Action key | Name | Target model (data-model_name) |\n| --- | --- | --- |\n"
            )
            for key, action in actions.items():
                result += f"| {key} | {action['website_form_label'] or action['name']} | {action['model']} |\n"
            result += (
                '\nCall this tool again with an action_key to list the model fields a '
                'form input `name` can bind to.'
            )
            return result
        action = actions.get(action_key)
        if not action:
            return f"Unknown form action '{action_key}'. Available actions: {', '.join(actions)}."
        fields_data = self.env['ir.model'].get_authorized_fields(action['model'], {})
        result = (
            f"The form action '{action_key}' ({action['website_form_label'] or action['name']}) "
            f"creates a '{action['model']}' record on submission "
            f"(the form's data-model_name must be \"{action['model']}\").\n"
            'Model fields a form input `name` can bind to (the visitor\'s input is '
            'written to the field):\n\n'
            "| Field | Label | Type | Required |\n| --- | --- | --- | --- |\n"
        )
        for name, field in sorted(fields_data.items()):
            if field.get('_property'):
                continue
            field_type = field.get('type', '')
            if field.get('selection'):
                values = ", ".join(f"'{key}' = {label}" for key, label in field['selection'])
                field_type += f" (option values: {values})"
            required = 'yes' if field.get('required') else ''
            result += f"| {name} | {field.get('string') or name} | {field_type} | {required} |\n"
        result += (
            "\nRequired fields MUST be present in the form (visible, or hidden with a "
            "value) or submissions fail.\n"
            "A relational field (many2one/many2many) can target a specific record "
            "invisibly: put it in a hidden s_website_form_dnone field with the record's "
            "numeric id as value (e.g. <input type=\"hidden\" name=\"project_id\" "
            "value=\"42\"/>); find the id with the retrieval tools.\n"
            "A visible input bound to a selection field must use the quoted keys above "
            "as its option `value`s, VERBATIM (the visible option text is free); one "
            "bound to a relational field uses the records' numeric ids.\n"
            "Never invent a field name: an input whose name is not listed above is a "
            "free-text answer stored as plain text, not data. Use such custom fields "
            "for any question no listed field covers."
        )
        if action['model'] == 'mail.mail':
            website = self.env['ai.website.service']._current_website()
            company_email = (website.company_id.email or self.env.company.email or '').strip()
            result += (
                "\nThe hidden email_to input's value is the address that receives the "
                "submissions; it must ALWAYS be chosen by the user. "
                + (f"The company address is {company_email} - offer it as the "
                   "recommended choice when asking."
                   if company_email else
                   "The company has no address configured - ask the user which "
                   "address to use.")
            )
        return result
