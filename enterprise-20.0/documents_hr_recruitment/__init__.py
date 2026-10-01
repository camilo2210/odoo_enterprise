# -*- coding: utf-8 -*-

from . import models

def _documents_hr_recruitment_post_init(env):
    env['res.company'].search([('recruitment_folder_id', '=', False)]).recruitment_folder_id = env.ref(
        'documents_hr_recruitment.document_recruitment_folder')
