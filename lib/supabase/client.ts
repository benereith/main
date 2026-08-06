import { createBrowserClient } from "@supabase/ssr";
import { supabaseKey, supabaseUrl } from "./konfiguriert";

export function createClient() {
  return createBrowserClient(supabaseUrl, supabaseKey);
}
