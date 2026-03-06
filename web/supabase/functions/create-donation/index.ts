import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import Stripe from "https://esm.sh/stripe@18.5.0";

const defaultAllowedOrigins = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:8080",
  "http://127.0.0.1:8080",
  "https://barnhousing.lovable.app",
  "https://id-preview--e20e731e-21f2-4fc0-9c1f-bb29005d4d43.lovable.app",
];

const configuredAllowedOrigins = (Deno.env.get("ALLOWED_ORIGINS") || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

const allowedOrigins = new Set([
  ...defaultAllowedOrigins,
  ...configuredAllowedOrigins,
]);

const isAllowedOrigin = (origin: string | null) => {
  if (!origin) {
    return true;
  }

  if (allowedOrigins.has(origin)) {
    return true;
  }

  try {
    return new URL(origin).hostname.endsWith(".lovable.app");
  } catch {
    return false;
  }
};

// Constants for validation
const MIN_DONATION = 1;
const MAX_DONATION = 100000; // $100,000 max

serve(async (req) => {
  const origin = req.headers.get("origin");
  const corsHeaders = {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
  const originAllowed = isAllowedOrigin(origin);

  // Handle CORS preflight requests
  if (req.method === "OPTIONS") {
    if (!originAllowed) {
      return new Response(
        JSON.stringify({ error: "Origin not allowed for donations." }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 403,
        }
      );
    }
    return new Response(null, { headers: corsHeaders });
  }

  if (!originAllowed) {
    return new Response(
      JSON.stringify({
        error: "Origin not allowed for donations. Add your domain to ALLOWED_ORIGINS.",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 403,
      }
    );
  }

  try {
    const { amount, recurring } = await req.json();

    // Validate amount - type check
    if (amount === undefined || amount === null || typeof amount !== "number") {
      return new Response(
        JSON.stringify({ error: "Invalid donation amount. Please enter a valid number." }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 400,
        }
      );
    }

    // Validate amount - range check
    if (!Number.isFinite(amount) || amount < MIN_DONATION || amount > MAX_DONATION) {
      return new Response(
        JSON.stringify({ error: `Invalid donation amount. Must be between $${MIN_DONATION} and $${MAX_DONATION.toLocaleString()}.` }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 400,
        }
      );
    }

    // Validate decimal precision (max 2 decimal places)
    const roundedAmount = Math.round(amount * 100) / 100;
    if (amount !== roundedAmount) {
      return new Response(
        JSON.stringify({ error: "Invalid donation amount. Maximum 2 decimal places allowed." }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 400,
        }
      );
    }

    const stripeSecretKey = Deno.env.get("STRIPE_SECRET_KEY");
    if (!stripeSecretKey) {
      return new Response(
        JSON.stringify({ error: "Donation service is not configured. Missing STRIPE_SECRET_KEY." }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 500,
        }
      );
    }

    // Initialize Stripe
    const stripe = new Stripe(stripeSecretKey, {
      apiVersion: "2025-08-27.basil",
    });

    const isRecurring = recurring === true;
    const originUrl = origin || Deno.env.get("SITE_URL");
    if (!originUrl) {
      return new Response(
        JSON.stringify({ error: "Unable to determine success URL. Set SITE_URL for server-side calls." }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 400,
        }
      );
    }
    const unitAmount = Math.round(amount * 100);
    const successUrl = isRecurring
      ? `${originUrl}/donation-success?recurring=true`
      : `${originUrl}/donation-success`;

    // Build Stripe Checkout session options
    const sessionOptions: Record<string, unknown> = {
      line_items: [
        {
          price_data: {
            currency: "usd",
            product_data: {
              name: isRecurring
                ? "Monthly Donation to Bay Area Renewal Network"
                : "Donation to Bay Area Renewal Network",
              description: isRecurring
                ? "Thank you for your recurring monthly support of our mission."
                : "Thank you for supporting our mission to transform abandoned properties into homes.",
            },
            unit_amount: unitAmount, // Convert to cents
            ...(isRecurring ? { recurring: { interval: "month" } } : {}),
          },
          quantity: 1,
        },
      ],
      mode: isRecurring ? "subscription" : "payment",
      success_url: successUrl,
      cancel_url: `${originUrl}/#donate`,
      ...(isRecurring ? {} : { submit_type: "donate" }),
    };

    const session = await stripe.checkout.sessions.create(sessionOptions);

    return new Response(JSON.stringify({ url: session.url }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 200,
    });
  } catch (error: unknown) {
    // Log detailed error server-side for debugging
    console.error("Error creating donation session:", error);

    // Return generic error message to client (don't expose internal details)
    return new Response(
      JSON.stringify({ error: "Unable to process donation. Please try again or contact support." }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 500,
      }
    );
  }
});
