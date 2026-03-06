import { CheckCircle, Home, Heart, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link, useSearchParams } from "react-router-dom";

const DonationSuccess = () => {
  const [searchParams] = useSearchParams();
  const isRecurring = searchParams.get("recurring") === "true";

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="max-w-lg text-center">
        <div className="w-20 h-20 rounded-full bg-barn-green/20 flex items-center justify-center mx-auto mb-8">
          {isRecurring ? (
            <RefreshCw size={48} className="text-barn-green" />
          ) : (
            <CheckCircle size={48} className="text-barn-green" />
          )}
        </div>

        <h1 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4">
          {isRecurring
            ? "Monthly Donation Set Up!"
            : "Thank You for Your Generosity!"}
        </h1>

        <p className="text-muted-foreground text-lg font-body mb-8">
          {isRecurring
            ? "Your recurring monthly donation to Bay Area Renewal Network has been set up successfully. Your continued support makes a lasting impact on families in need."
            : "Your donation to Bay Area Renewal Network will help transform abandoned properties into homes for families in need. Together, we're building stronger communities."}
        </p>

        <div className="bg-card rounded-2xl p-6 mb-8 shadow-soft">
          <div className="flex items-center justify-center gap-3 text-primary mb-3">
            <Heart size={20} />
            <span className="font-medium">Your Impact</span>
          </div>
          <p className="text-muted-foreground text-sm font-body">
            {isRecurring
              ? "You'll receive a confirmation email shortly with details about your monthly subscription. You can manage or cancel your donation anytime through the link in your confirmation email."
              : "You'll receive a confirmation email shortly. Your contribution directly supports our mission to help those in need through property renewal."}
          </p>
        </div>

        <Link to="/">
          <Button variant="hero" size="lg">
            <Home size={18} className="mr-2" />
            Return Home
          </Button>
        </Link>
      </div>
    </div>
  );
};

export default DonationSuccess;
