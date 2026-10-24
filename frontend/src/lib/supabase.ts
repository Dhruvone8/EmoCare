import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://mycmrvzjeewfsencehrn.supabase.co";
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15Y21ydnpqZWV3ZnNlbmNlaHJuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY3MjAxNzUsImV4cCI6MjEwMjI5NjE3NX0.tg0xx2Dt9j1uHtWtGcrBMWam2gR4IPFfauPHNkEr4K0";

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});
