from lxml import etree
from hashlib import sha256
from collections import defaultdict

from odoo import http
from odoo.http import request
from odoo.fields import Domain

from odoo.addons.web_studio.controllers.report import STUDIO_VIEW_DIFF_KEY_TEMPLATE, _get_arch_without_studio


def digest_term(term):
    return sha256(term.encode()).hexdigest()

class WebStudioController(http.Controller):

    @http.route("/web_studio/get_view_translations", type="jsonrpc", auth="user")
    def _get_view_translations(self, view_id, target_lang=None, field_name="arch"):
        base_lang = self.env["ir.ui.view"].browse(view_id)._get_base_lang()
        langs = self.env["res.lang"].sudo()._get_active_langs().sorted('name')
        lang_codes = [l.code for l in langs]
        if target_lang is None or target_lang not in lang_codes:
            target_lang = next(iter(code for code in lang_codes if code != base_lang), None)
        view = self.env["ir.ui.view"].with_context(lang=target_lang).browse(view_id)
        # Get the combined arch with the term wrapped into "branded" spans
        if field_name == "combined_arch":
            xml_value = view.with_context(edit_translations=True).get_combined_arch()
        else:
            xml_value = view.with_context(edit_translations=True).arch_db
        languages = {l.code: {"name": l.name, "direction": l.direction, "is_base": l.code == base_lang} for l in langs}
        return dict(
            translation_mode="xml",
            xml_values={target_lang: xml_value},
            languages=languages,
        )

    @http.route("/web_studio/save_view_translations", type="jsonrpc", auth="user")
    def _save_view_translation(self, view_id, field_name, changes, target_lang=None):
        to_save = defaultdict(lambda: defaultdict(dict))
        for res_id, lang_data in changes.items():
            for lang, sha_data in lang_data.items():
                for sha, value in sha_data.items():
                    to_save[int(res_id)][lang][sha] = value
        for res_id, update_tr in to_save.items():
            self.env["ir.ui.view"].browse(res_id)._update_field_translations("arch_db", update_tr, digest=digest_term)

    @http.route("/web_studio/get_report_resources", type="jsonrpc", auth="user")
    def get_report_resources(self, key):
        View = request.env["ir.ui.view"].with_context(lang=None, active_test=False)
        key_to_view = {}
        main_view = None
        xml_ids = [[key]]
        view_fields_to_read = ["id", "active", "inherit_id", "key", "xml_id", "arch", "name"]
        for keys in xml_ids:
            root_views = View.browse([View._get_template_view(x_id).id for x_id in keys if x_id not in key_to_view])
            if root_views:
                studio_views = View.search(
                    Domain.AND([
                        Domain("inherit_id", "in", root_views.ids),
                        Domain("key", "in", [STUDIO_VIEW_DIFF_KEY_TEMPLATE.format(key=v.key) for v in root_views])
                    ]),
                    order="priority desc, id desc"
                )

                # Add Studio Customizations to final result
                studio_key_map = {}
                for studio_view, data in zip(studio_views, studio_views.read(view_fields_to_read)):
                    if not data["active"]:
                        data["invalid_locators"] = studio_view.invalid_locators
                    key_to_view[studio_view.xml_id] = data
                    studio_key_map[studio_view.key] = studio_view

                for root, root_data in zip(root_views, root_views.read(view_fields_to_read)):
                    key_to_view[root_data["xml_id"]] = root_data
                    root_data["called_xml_ids"] = []
                    studio_view = studio_key_map.get(STUDIO_VIEW_DIFF_KEY_TEMPLATE.format(key=root.key), View)
                    try:
                        arch, studio_arch = _get_arch_without_studio(root, studio_view)
                        tree = View._prepare_arch_for_diff(arch, studio_arch if studio_view.active else None, "lock-id")
                    except ValueError as e:
                        if hasattr(e, "context"):
                            view_in_error = e.context.get("view", View)
                            inheriting_views = root._get_inheriting_views() | view_in_error
                            # Most probably an inheritance error: get and show every view involved
                            # the list [v.inherit_id.id] may yield [False] which is good
                            # it will indicate to edit the raw arch, not the combined arch
                            for inherit_data in inheriting_views.read(view_fields_to_read + ["invalid_locators"]):
                                inherit_arch = etree.fromstring(inherit_data["arch"])
                                main_view_, called_xml_ids = self._extract_tcalled_xml_ids(inherit_arch, main_view)
                                main_view = main_view_ or main_view
                                if called_xml_ids:
                                    root_data["called_xml_ids"].extend(called_xml_ids)
                                    xml_ids.append(called_xml_ids)
                                key_to_view[inherit_data["xml_id"] or inherit_data["id"]] = inherit_data
                        else:
                            raise
                        continue
                    root_data["combined_arch"] = etree.tostring(tree, encoding="unicode")
                    main_view_, called_xml_ids = self._extract_tcalled_xml_ids(tree, main_view)
                    main_view = main_view_ or main_view
                    if called_xml_ids:
                        root_data["called_xml_ids"] = called_xml_ids
                        xml_ids.append(called_xml_ids)

        return {
            "main_view_key": main_view or key,
            "views": list(key_to_view.values()),
        }

    @http.route("/web_studio/get_xml_editor_resources", type="jsonrpc", auth="user")
    def get_xml_editor_resources(self, key):
        View = request.env["ir.ui.view"].with_context(no_primary_children=True, __views_get_original_hierarchy=[], active_test=True)
        views = View.get_related_views(key)
        views = views.read(['name', 'id', 'key', 'xml_id', 'arch', 'active', 'inherit_id'])

        main_view = None
        for view in views:
            arch = view["arch"]
            if not arch or not arch.strip():
                continue
            root = etree.fromstring(arch)
            main_view_, _ = self._extract_tcalled_xml_ids(root, main_view)
            main_view = main_view_ or main_view

        return {
            "main_view_key": main_view or key,
            "views": views,
        }

    def _extract_tcalled_xml_ids(self, tree, main_view=False):
        called_xml_ids = []
        for el in tree.xpath("//*[@t-call]"):
            tcall = el.get("t-call")
            if "{" in tcall:
                continue
            called_xml_ids.append(tcall)
            if main_view is None and el.xpath("ancestor::t[@t-foreach='docs']"):
                main_view = tcall
        return main_view, called_xml_ids
