-- Replace raw ip_address INET (PII) with a SHA-256 prefix hash (TEXT).
-- Existing rows get ip_address_hash = NULL to comply with DSGVO Art. 5(1)(c).
ALTER TABLE user_consents
    ADD COLUMN ip_address_hash TEXT;

UPDATE user_consents SET ip_address_hash = NULL;

ALTER TABLE user_consents DROP COLUMN ip_address;
