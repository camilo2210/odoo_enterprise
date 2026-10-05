-- disable AvaTax
UPDATE res_company
   SET avalara_environment = 'sandbox';
UPDATE account_fiscal_position
   SET is_avatax = false;

UPDATE res_company
   SET avalara_iap_connected = false;
DELETE FROM account_edi_proxy_client_user
      WHERE proxy_type = 'avatax';
