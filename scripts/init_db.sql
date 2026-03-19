-- This runs automatically when PostgreSQL container first starts
-- Enables the pgcrypto extension used for AES-256 column encryption

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Encryption helper function: wraps pgcrypto for column-level AES-256 encryption
-- Usage: SELECT encrypt_data('sensitive text', current_setting('app.encryption_key'))
CREATE OR REPLACE FUNCTION encrypt_data(plaintext TEXT, key TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN pgp_sym_encrypt(plaintext, key, 'cipher-algo=aes256');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION decrypt_data(ciphertext BYTEA, key TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(ciphertext, key);
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL; -- Decryption failed (wrong key)
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
