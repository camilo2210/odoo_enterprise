DELETE FROM ir_config_parameter WHERE key = 'l10n_au_payroll_iap.endpoint';
UPDATE res_company SET l10n_au_payroll_mode = 'test';
UPDATE l10n_au_employer_registration SET status = 'expired' WHERE status = 'registered';
DELETE FROM account_edi_proxy_client_user WHERE proxy_type = 'l10n_au_payroll';
