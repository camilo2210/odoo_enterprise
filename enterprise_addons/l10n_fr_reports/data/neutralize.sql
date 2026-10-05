-- Disable l10n_fr_reports ASPOne production mode
INSERT INTO ir_config_parameter (key, value)
     VALUES ('l10n_fr_reports.aspone_mode', 'test')
ON CONFLICT (key) DO UPDATE
        SET VALUE = 'test';
