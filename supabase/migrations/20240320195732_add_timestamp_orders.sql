alter table "public"."drafts" drop constraint "public_drafts_address_id_fkey";

alter table "public"."messages" drop constraint "public_messages_order_referenced_fkey";

alter table "public"."orders" drop constraint "public_orders_address_id_fkey";

alter table "public"."orders" drop constraint "public_orders_message_id_fkey";

alter table "public"."addresses" alter column "created_at" drop default;

alter table "public"."addresses" alter column "created_at" set data type timestamp with time zone using "created_at"::timestamp with time zone;

alter table "public"."drafts" alter column "created_at" drop default;

alter table "public"."drafts" alter column "created_at" set data type timestamp with time zone using "created_at"::timestamp with time zone;

alter table "public"."messages" alter column "timestamp" drop default;

alter table "public"."messages" alter column "timestamp" set data type timestamp with time zone using "timestamp"::timestamp with time zone;

alter table "public"."orders" add column "created_at" timestamp with time zone default (now() AT TIME ZONE 'utc'::text);

alter table "public"."users" alter column "created_at" drop default;

alter table "public"."users" alter column "created_at" set data type timestamp with time zone using "created_at"::timestamp with time zone;

alter table "public"."drafts" add constraint "drafts_address_id_fkey" FOREIGN KEY (address_id) REFERENCES addresses(address_id) ON DELETE SET NULL not valid;

alter table "public"."drafts" validate constraint "drafts_address_id_fkey";

alter table "public"."messages" add constraint "messages_order_referenced_fkey" FOREIGN KEY (order_referenced) REFERENCES orders(order_id) ON DELETE SET NULL not valid;

alter table "public"."messages" validate constraint "messages_order_referenced_fkey";

alter table "public"."orders" add constraint "orders_address_id_fkey" FOREIGN KEY (address_id) REFERENCES addresses(address_id) ON DELETE SET NULL not valid;

alter table "public"."orders" validate constraint "orders_address_id_fkey";

alter table "public"."orders" add constraint "orders_message_id_fkey" FOREIGN KEY (message_id) REFERENCES messages(message_id) not valid;

alter table "public"."orders" validate constraint "orders_message_id_fkey";
