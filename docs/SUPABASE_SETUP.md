# Supabase setup for QORE

QORE is configured for the Supabase project URL:

`https://yxelmlwtggjgbvjpkmrx.supabase.co`

The URL belongs in the server environment only. Copy `.env.example` to `.env` and provide the publishable/anon key there. Never put either key in `frontend/` or a `VITE_*` variable. Never commit a service-role key.

## Apply the schema

Run the migration in `supabase/migrations/202610240001_qore_ledger.sql` from the Supabase SQL editor or an authenticated Supabase migration workflow. It enables RLS and limits every row to its `owner_id`.

## Configure providers

In Supabase Authentication settings, enable Email and Google providers and set the QORE callback URL for the deployed frontend. Passwords remain inside Supabase Auth; QORE never stores password material.

The local SQLite ledger remains the fallback until the backend is explicitly switched to the authenticated Supabase client. No cloud writes are attempted merely from a project URL.
