-- disable l10n_de_pos_cert (Fiskaly)
UPDATE res_company
   SET l10n_de_fiskaly_api_key = NULL,
       l10n_de_fiskaly_api_secret = NULL,
       l10n_de_fiskaly_organization_id = NULL;

UPDATE pos_config
    SET l10n_de_fiskaly_tss_id = NULL,
        l10n_de_fiskaly_client_id = NULL,
        l10n_de_create_tss_flag = false;
