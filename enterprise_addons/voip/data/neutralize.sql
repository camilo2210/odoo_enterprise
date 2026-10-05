-- disable voip
UPDATE voip_provider
   SET mode = 'demo';

-- clear phone service client credentials
DELETE FROM ir_config_parameter
 WHERE key IN ('voip.client_uuid', 'voip.client_secret');
