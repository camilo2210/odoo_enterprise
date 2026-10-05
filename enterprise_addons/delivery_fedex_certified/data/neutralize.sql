-- Disable FedEx REST connector by wiping account credentials
UPDATE fedex_certified_account
   SET child_key = 'dummy',
       child_secret = 'dummy',
       auth_token = NULL,
       auth_token_expiration = NULL;
