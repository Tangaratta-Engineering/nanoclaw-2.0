-- Health claims datastore (database "claims" on hp-db). Idempotent: safe to run on every start.
CREATE TABLE IF NOT EXISTS allowed_providers (
  provider_key  text PRIMARY KEY,           -- normalised practice name, see normProvider() in ops.mjs
  display_name  text NOT NULL,
  added_at      timestamptz NOT NULL DEFAULT now(),
  removed_at    timestamptz,                -- soft delete: the history stays
  note          text
);
CREATE TABLE IF NOT EXISTS patients (        -- names that count as "one of ours"; anything else is flagged. Filled in privately (not in git): INSERT INTO patients VALUES ('<first last, lower case>', '<Display Name>')
  name_key      text PRIMARY KEY,
  display_name  text NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
  id            serial PRIMARY KEY,
  provider_key  text NOT NULL,
  provider_name text NOT NULL,
  patient_name  text NOT NULL,
  patient_known boolean NOT NULL,
  invoice_no    text NOT NULL,
  invoice_date  date,
  amount_cents  integer,
  service       text,
  reference     text NOT NULL,              -- text typed into Peoplecare's Reference box
  email_id      text,                       -- Gmail message id the invoice came from
  pdf_path      text NOT NULL,
  pdf_sha256    text NOT NULL UNIQUE,
  status        text NOT NULL CHECK (status IN ('pending_provider','ready','prepared','submitted','failed','cancelled')),
  approval_code text,                       -- set by prepare, must be quoted back by George to submit
  peoplecare_ref text,                      -- e.g. Claim_1795132504142
  error         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  prepared_at   timestamptz,
  submitted_at  timestamptz,
  UNIQUE (provider_key, invoice_no)
);
CREATE TABLE IF NOT EXISTS claim_log (
  id        serial PRIMARY KEY,
  claim_id  integer REFERENCES claims(id),
  at        timestamptz NOT NULL DEFAULT now(),
  event     text NOT NULL,
  detail    text
);
