-- neutralize Infile
UPDATE res_company
   SET l10n_do_edi_web_service_env = 'demo',
       l10n_do_edi_username = NULL,
       l10n_do_edi_password = NULL,
       l10n_do_edi_key = NULL,
       l10n_do_edi_llave = NULL;
