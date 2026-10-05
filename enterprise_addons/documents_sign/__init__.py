# -*- coding: utf-8 -*-

from . import models
from . import wizard


def _post_init_hook(env):
    """Post-init hook to embed the Sign action into standard document folders."""
    sign_action = env.ref("documents_sign.ir_actions_server_create_sign_template_direct", raise_if_not_found=False)
    if not sign_action:
        return

    folder_xml_ids = [
        # General
        "documents.document_internal_folder",
        "documents.document_inbox_folder",
        "documents_sign.document_sign_folder",
        # Legal
        "documents.document_legal_folder",
        "documents.document_insurances_folder",
        "documents.document_loans_folder",
        "documents.document_registrations_folder",
        "documents.document_contracts_folder",
        # Finance
        "documents.document_finance_folder",
        "documents.document_finance_social_folder",
        "documents.document_finance_taxes_folder",
        "documents.document_finance_annual_closing_folder",
        "documents.document_finance_annual_closing_year_current_folder",
    ]

    folders_to_process = env['documents.document']

    for xml in folder_xml_ids:
        folder = env.ref(xml, raise_if_not_found=False)
        if folder and folder.active:
            folders_to_process |= folder

    if folders_to_process:
        folders_to_process._embed_action(sign_action.id)
