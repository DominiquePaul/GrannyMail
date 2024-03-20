
SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE EXTENSION IF NOT EXISTS "pgsodium" WITH SCHEMA "pgsodium";

CREATE SCHEMA IF NOT EXISTS "public";

ALTER SCHEMA "public" OWNER TO "pg_database_owner";

CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";

CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";

SET default_tablespace = '';

SET default_table_access_method = "heap";

CREATE TABLE IF NOT EXISTS "public"."addresses" (
    "address_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "created_at" timestamp without time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text"),
    "addressee" character varying,
    "address_line1" character varying,
    "address_line2" character varying,
    "zip" character varying,
    "city" character varying,
    "country" character varying
);

ALTER TABLE "public"."addresses" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."drafts" (
    "draft_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "created_at" timestamp without time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text"),
    "text" "text",
    "blob_path" character varying,
    "address_id" "uuid",
    "builds_on" "uuid"
);

ALTER TABLE "public"."drafts" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."files" (
    "message_id" "uuid" NOT NULL,
    "mime_type" character varying,
    "blob_path" character varying,
    "file_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL
);

ALTER TABLE "public"."files" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."messages" (
    "message_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid",
    "timestamp" timestamp without time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text"),
    "sent_by" character varying,
    "message_body" "text",
    "attachment_mime_type" character varying,
    "memo_duration" real,
    "transcript" "text",
    "command" character varying,
    "draft_referenced" "uuid",
    "message_type" character varying,
    "tg_user_id" character varying,
    "tg_chat_id" bigint,
    "tg_message_id" character varying,
    "wa_mid" character varying,
    "wa_webhook_id" character varying,
    "wa_phone_number_id" character varying,
    "wa_profile_name" character varying,
    "wa_media_id" character varying,
    "wa_reference_wamid" character varying,
    "wa_reference_message_user_phone" character varying,
    "phone_number" character varying,
    "action_confirmed" boolean,
    "response_to" "uuid",
    "messaging_platform" character varying,
    "order_referenced" "uuid"
);

ALTER TABLE "public"."messages" OWNER TO "postgres";

COMMENT ON TABLE "public"."messages" IS 'Tracks all messages sent by the system and by users';

CREATE TABLE IF NOT EXISTS "public"."orders" (
    "order_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "draft_id" "uuid",
    "address_id" "uuid",
    "status" character varying,
    "payment_type" character varying,
    "message_id" "uuid",
    "blob_path" "text"
);

ALTER TABLE "public"."orders" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."system_messages" (
    "message_identifier" "text" NOT NULL,
    "message_body" "text" NOT NULL
);

ALTER TABLE "public"."system_messages" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."users" (
    "user_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp without time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text"),
    "first_name" character varying,
    "last_name" character varying,
    "email" character varying,
    "phone_number" character varying,
    "telegram_id" character varying,
    "prompt" "text",
    "num_letter_credits" bigint DEFAULT '0'::bigint
);

ALTER TABLE "public"."users" OWNER TO "postgres";

ALTER TABLE ONLY "public"."addresses"
    ADD CONSTRAINT "addresses_pkey" PRIMARY KEY ("address_id");

ALTER TABLE ONLY "public"."drafts"
    ADD CONSTRAINT "drafts_pkey" PRIMARY KEY ("draft_id");

ALTER TABLE ONLY "public"."files"
    ADD CONSTRAINT "files_pkey" PRIMARY KEY ("file_id");

ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_pkey" PRIMARY KEY ("message_id");

ALTER TABLE ONLY "public"."orders"
    ADD CONSTRAINT "orders_pkey" PRIMARY KEY ("order_id");

ALTER TABLE ONLY "public"."system_messages"
    ADD CONSTRAINT "system_messages_pkey" PRIMARY KEY ("message_identifier");

ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_email_key" UNIQUE ("email");

ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("user_id");

ALTER TABLE ONLY "public"."addresses"
    ADD CONSTRAINT "addresses_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("user_id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."drafts"
    ADD CONSTRAINT "drafts_builds_on_fkey" FOREIGN KEY ("builds_on") REFERENCES "public"."drafts"("draft_id");

ALTER TABLE ONLY "public"."drafts"
    ADD CONSTRAINT "drafts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("user_id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."files"
    ADD CONSTRAINT "files_message_id_fkey" FOREIGN KEY ("message_id") REFERENCES "public"."messages"("message_id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_draft_referenced_fkey" FOREIGN KEY ("draft_referenced") REFERENCES "public"."drafts"("draft_id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_response_to_fkey" FOREIGN KEY ("response_to") REFERENCES "public"."messages"("message_id");

ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("user_id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."orders"
    ADD CONSTRAINT "orders_draft_id_fkey" FOREIGN KEY ("draft_id") REFERENCES "public"."drafts"("draft_id");

ALTER TABLE ONLY "public"."orders"
    ADD CONSTRAINT "orders_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("user_id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."drafts"
    ADD CONSTRAINT "public_drafts_address_id_fkey" FOREIGN KEY ("address_id") REFERENCES "public"."addresses"("address_id") ON DELETE SET NULL;

ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "public_messages_order_referenced_fkey" FOREIGN KEY ("order_referenced") REFERENCES "public"."orders"("order_id") ON DELETE SET NULL;

ALTER TABLE ONLY "public"."orders"
    ADD CONSTRAINT "public_orders_address_id_fkey" FOREIGN KEY ("address_id") REFERENCES "public"."addresses"("address_id") ON DELETE SET NULL;

ALTER TABLE ONLY "public"."orders"
    ADD CONSTRAINT "public_orders_message_id_fkey" FOREIGN KEY ("message_id") REFERENCES "public"."messages"("message_id");

ALTER TABLE "public"."addresses" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."drafts" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."files" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."messages" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."orders" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."system_messages" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;

REVOKE USAGE ON SCHEMA "public" FROM PUBLIC;
GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

GRANT ALL ON TABLE "public"."addresses" TO "anon";
GRANT ALL ON TABLE "public"."addresses" TO "authenticated";
GRANT ALL ON TABLE "public"."addresses" TO "service_role";

GRANT ALL ON TABLE "public"."drafts" TO "anon";
GRANT ALL ON TABLE "public"."drafts" TO "authenticated";
GRANT ALL ON TABLE "public"."drafts" TO "service_role";

GRANT ALL ON TABLE "public"."files" TO "anon";
GRANT ALL ON TABLE "public"."files" TO "authenticated";
GRANT ALL ON TABLE "public"."files" TO "service_role";

GRANT ALL ON TABLE "public"."messages" TO "anon";
GRANT ALL ON TABLE "public"."messages" TO "authenticated";
GRANT ALL ON TABLE "public"."messages" TO "service_role";

GRANT ALL ON TABLE "public"."orders" TO "anon";
GRANT ALL ON TABLE "public"."orders" TO "authenticated";
GRANT ALL ON TABLE "public"."orders" TO "service_role";

GRANT ALL ON TABLE "public"."system_messages" TO "anon";
GRANT ALL ON TABLE "public"."system_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."system_messages" TO "service_role";

GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";

RESET ALL;
