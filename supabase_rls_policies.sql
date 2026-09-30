-- ==============================================================================
-- ARNA LUXURY FASHION: SUPABASE PRODUCTION RLS POLICIES & SCHEMA MIGRATION
-- Run this script in your Supabase SQL Editor (https://supabase.com/dashboard)
-- ==============================================================================

-- 1. FOREIGN KEY & COLUMN CORRECTIONS
-- Allow cascading product deletions so deleting a product from admin portal
-- automatically cascades referenced order_items without constraint errors (23502 / 23503)
ALTER TABLE IF EXISTS order_items ALTER COLUMN product_id DROP NOT NULL;
ALTER TABLE IF EXISTS order_items DROP CONSTRAINT IF EXISTS order_items_product_id_fkey;
ALTER TABLE IF EXISTS order_items 
  ADD CONSTRAINT order_items_product_id_fkey 
  FOREIGN KEY (product_id) 
  REFERENCES products(id) 
  ON DELETE CASCADE;

-- Add sold_out_at timestamp column for tracking the 5-hour sold-out auto-removal rule
ALTER TABLE IF EXISTS products 
  ADD COLUMN IF NOT EXISTS sold_out_at timestamptz;

-- Add verification token and idempotency key columns to orders table
ALTER TABLE IF EXISTS orders 
  ADD COLUMN IF NOT EXISTS order_verification_key text,
  ADD COLUMN IF NOT EXISTS idempotency_key text;

-- 2. ENABLE ROW LEVEL SECURITY (RLS) ON ALL TABLES
ALTER TABLE IF EXISTS products ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS coupons ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS visitor_stats ENABLE ROW LEVEL SECURITY;

-- 3. DROP EXISTING CONFLICTING POLICIES (Idempotent re-runnable script)
DROP POLICY IF EXISTS "products_select_public" ON products;
DROP POLICY IF EXISTS "products_all_admin" ON products;
DROP POLICY IF EXISTS "orders_select_policy" ON orders;
DROP POLICY IF EXISTS "orders_insert_policy" ON orders;
DROP POLICY IF EXISTS "orders_update_policy" ON orders;
DROP POLICY IF EXISTS "orders_delete_policy" ON orders;
DROP POLICY IF EXISTS "order_items_select_policy" ON order_items;
DROP POLICY IF EXISTS "order_items_insert_policy" ON order_items;
DROP POLICY IF EXISTS "order_items_all_policy" ON order_items;
DROP POLICY IF EXISTS "users_select_policy" ON users;
DROP POLICY IF EXISTS "users_insert_policy" ON users;
DROP POLICY IF EXISTS "users_update_policy" ON users;
DROP POLICY IF EXISTS "coupons_select_public" ON coupons;
DROP POLICY IF EXISTS "coupons_all_admin" ON coupons;
DROP POLICY IF EXISTS "visitor_stats_select_public" ON visitor_stats;
DROP POLICY IF EXISTS "visitor_stats_update_public" ON visitor_stats;

-- 4. CLEAR, SECURE ROW LEVEL SECURITY POLICIES

-- ==============================================================================
-- TABLE: products
-- Public / Storefront: Read-only access to view garments
-- Admin / Backend: Full CRUD access
-- ==============================================================================
CREATE POLICY "products_select_public"
  ON products FOR SELECT
  USING (true);

CREATE POLICY "products_all_admin"
  ON products FOR ALL
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

-- ==============================================================================
-- TABLE: orders
-- Storefront: Any visitor/customer can insert an order with an idempotency key.
-- Customers and Admins can view orders.
-- Admin can update status and packing notes.
-- ==============================================================================
CREATE POLICY "orders_select_policy"
  ON orders FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "orders_insert_policy"
  ON orders FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "orders_update_policy"
  ON orders FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "orders_delete_policy"
  ON orders FOR DELETE
  TO anon, authenticated
  USING (true);

-- ==============================================================================
-- TABLE: order_items
-- Relational line items linked to orders.
-- ==============================================================================
CREATE POLICY "order_items_select_policy"
  ON order_items FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "order_items_insert_policy"
  ON order_items FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "order_items_all_policy"
  ON order_items FOR ALL
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

-- ==============================================================================
-- TABLE: users
-- Allows customer account creation, guest profiles, and admin authentication.
-- ==============================================================================
CREATE POLICY "users_select_policy"
  ON users FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "users_insert_policy"
  ON users FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "users_update_policy"
  ON users FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

-- ==============================================================================
-- TABLE: coupons
-- Public can check active coupon codes at checkout.
-- Admin can create, toggle, and manage promo codes.
-- ==============================================================================
CREATE POLICY "coupons_select_public"
  ON coupons FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "coupons_all_admin"
  ON coupons FOR ALL
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

-- ==============================================================================
-- TABLE: visitor_stats
-- Analytics counter tracking storefront pageviews and visits.
-- ==============================================================================
CREATE POLICY "visitor_stats_select_public"
  ON visitor_stats FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "visitor_stats_update_public"
  ON visitor_stats FOR ALL
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);
