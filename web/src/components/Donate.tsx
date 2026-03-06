import { useState } from "react";
import { Heart, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "@/hooks/use-toast";

const suggestedAmounts = [25, 50, 100, 250];

const normalizeCurrencyInput = (value: string) => {
  const cleaned = value.replace(/[^0-9.]/g, "");
  const [whole = "", ...decimalParts] = cleaned.split(".");

  if (decimalParts.length === 0) {
    return whole;
  }

  const decimals = decimalParts.join("").slice(0, 2);
  return `${whole || "0"}.${decimals}`;
};

const Donate = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedAmount, setSelectedAmount] = useState<number | null>(null);
  const [customAmount, setCustomAmount] = useState("");
  const [isRecurring, setIsRecurring] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleAmountSelect = (amount: number) => {
    setSelectedAmount(amount);
    setCustomAmount("");
  };

  const handleCustomAmountChange = (value: string) => {
    setCustomAmount(normalizeCurrencyInput(value));
    setSelectedAmount(null);
  };

  const getFinalAmount = (): number | null => {
    if (selectedAmount) return selectedAmount;
    if (customAmount) {
      const parsed = Number.parseFloat(customAmount);
      if (!Number.isFinite(parsed)) {
        return null;
      }
      return parsed >= 1 ? Math.round(parsed * 100) / 100 : null;
    }
    return null;
  };

  const handleDonate = async () => {
    const amount = getFinalAmount();
    if (!amount || amount < 1) {
      toast({
        title: "Invalid Amount",
        description: "Please select or enter a valid donation amount.",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
      const { data, error } = await supabase.functions.invoke<{ url?: string; error?: string }>("create-donation", {
        body: { amount, recurring: isRecurring },
      });

      if (error) {
        throw new Error(error.message);
      }

      if (data?.error) {
        throw new Error(data.error);
      }

      if (!data?.url) {
        throw new Error("Unable to start checkout. Please try again.");
      }

      // Same-tab redirect avoids popup blockers.
      window.location.assign(data.url);
    } catch (error) {
      const description = error instanceof Error
        ? error.message
        : "Unable to process donation. Please try again.";
      if (import.meta.env.DEV) {
        console.error("Donation error:", error);
      }
      toast({
        title: "Error",
        description,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const finalAmount = getFinalAmount();

  return (
    <section id="donate" className="section-padding bg-barn-gold/5">
      <div className="container-wide">
        <div className="max-w-4xl mx-auto text-center">
          <span className="text-primary font-medium text-sm uppercase tracking-wider">Support Our Mission</span>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mt-4 mb-6">
            Make a <span className="text-gradient">Difference</span> Today
          </h2>
          <p className="text-muted-foreground text-lg font-body max-w-2xl mx-auto mb-8">
            Your contribution helps transform abandoned properties into welcoming homes
            and gives families a fresh start. Every dollar makes an impact.
          </p>

          <Button
            variant="hero"
            size="xl"
            onClick={() => setIsOpen(true)}
          >
            <Heart size={20} className="mr-2" />
            Donate Now
          </Button>

          <p className="text-muted-foreground text-sm mt-6 font-body">
            Your donation directly supports our mission to help those in need through property renewal.
          </p>
        </div>
      </div>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl">Make a Donation</DialogTitle>
            <DialogDescription>
              Choose a suggested amount or enter your own.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-3 my-4">
            {suggestedAmounts.map((amount) => (
              <button
                key={amount}
                onClick={() => handleAmountSelect(amount)}
                className={`p-4 rounded-xl border-2 transition-all duration-200 font-display text-xl font-bold ${selectedAmount === amount
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border hover:border-primary/50 text-foreground"
                  }`}
              >
                ${amount}
              </button>
            ))}
          </div>

          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-medium">$</span>
            <Input
              type="text"
              inputMode="decimal"
              placeholder="Enter custom amount"
              value={customAmount}
              onChange={(e) => handleCustomAmountChange(e.target.value)}
              className="pl-7 text-lg"
            />
          </div>

          {/* One-time / Monthly toggle */}
          <div className="flex rounded-xl border-2 border-border overflow-hidden mt-4">
            <button
              onClick={() => setIsRecurring(false)}
              className={`flex-1 py-3 px-4 text-sm font-semibold transition-all duration-200 ${!isRecurring
                  ? "bg-primary text-primary-foreground"
                  : "bg-transparent text-muted-foreground hover:text-foreground"
                }`}
            >
              One-time
            </button>
            <button
              onClick={() => setIsRecurring(true)}
              className={`flex-1 py-3 px-4 text-sm font-semibold transition-all duration-200 flex items-center justify-center gap-1.5 ${isRecurring
                  ? "bg-primary text-primary-foreground"
                  : "bg-transparent text-muted-foreground hover:text-foreground"
                }`}
            >
              <RefreshCw size={14} />
              Monthly
            </button>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-border mt-4">
            <div>
              <p className="text-sm text-muted-foreground">
                {isRecurring ? "Monthly Total" : "Total"}
              </p>
              <p className="font-display text-2xl font-bold text-foreground">
                ${finalAmount || 0}
                {isRecurring && (
                  <span className="text-sm font-normal text-muted-foreground">/month</span>
                )}
              </p>
            </div>
            <Button
              variant="hero"
              onClick={handleDonate}
              disabled={isLoading || !finalAmount}
            >
              {isRecurring ? (
                <RefreshCw size={18} className="mr-2" />
              ) : (
                <Heart size={18} className="mr-2" />
              )}
              {isLoading
                ? "Processing..."
                : isRecurring
                  ? "Donate Monthly"
                  : "Complete Donation"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
};

export default Donate;
