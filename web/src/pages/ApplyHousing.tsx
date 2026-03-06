import { useState } from "react";
import { Heart, Home, Shield, Users, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import HousingApplicationForm from "@/components/HousingApplicationForm";

const eligibility = [
  "Currently in need of stable housing",
  "Family with children or expecting a child",
  "Legal right to reside in the United States",
  "Willingness to participate in our housing program requirements",
  "Commitment to maintaining the property and being a good neighbor",
];

const programFeatures = [
  {
    icon: Home,
    title: "Stable Housing",
    description: "Move into a renovated home with all utilities ready. You'll have a safe place to live while helping maintain the property.",
  },
  {
    icon: Users,
    title: "Ongoing Support",
    description: "Access to community resources and a support network. We're here to help you succeed in the program.",
  },
  {
    icon: Shield,
    title: "Path to Stability",
    description: "Build skills, savings, and housing history while contributing to your community as a property caretaker.",
  },
];

const processSteps = [
  {
    step: "1",
    title: "Apply",
    description: "Complete our housing application with information about your family and current situation.",
  },
  {
    step: "2",
    title: "Interview",
    description: "Meet with our team to discuss your needs and learn more about our program.",
  },
  {
    step: "3",
    title: "Matching",
    description: "We carefully match you with an available property that fits your family's needs.",
  },
  {
    step: "4",
    title: "Move In",
    description: "Receive keys to your new home and begin your journey toward stability.",
  },
];

const ApplyHousing = () => {
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-20">
        {/* Hero Section */}
        <section className="section-padding bg-accent text-primary-foreground">
          <div className="container-wide">
            <Link to="/#get-involved" className="inline-flex items-center gap-2 text-primary-foreground/80 hover:text-primary-foreground mb-6 transition-colors">
              <ArrowLeft size={18} />
              Back to Get Involved
            </Link>
            <div className="max-w-3xl">
              <div className="w-16 h-16 rounded-2xl bg-primary-foreground/20 flex items-center justify-center mb-6">
                <Heart size={32} className="text-primary-foreground" />
              </div>
              <h1 className="font-display text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Become a Caretaker
              </h1>
              <p className="text-lg md:text-xl text-primary-foreground/90 font-body">
                If you or your family is in need of stable housing, our Caretaker Program may be right for you. You help maintain a property in exchange for a place to call home.
              </p>
            </div>
          </div>
        </section>

        {/* Program Features */}
        <section className="section-padding">
          <div className="container-wide">
            <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-12 text-center">
              What Our Program Offers
            </h2>
            <div className="grid md:grid-cols-3 gap-8 mb-16">
              {programFeatures.map((feature) => (
                <div key={feature.title} className="bg-card rounded-2xl p-8 shadow-soft">
                  <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center mb-4">
                    <feature.icon size={24} className="text-accent" />
                  </div>
                  <h3 className="font-display text-xl font-bold text-foreground mb-3">{feature.title}</h3>
                  <p className="text-muted-foreground font-body">{feature.description}</p>
                </div>
              ))}
            </div>

            {/* Process Steps */}
            <div className="bg-muted rounded-3xl p-8 md:p-12 mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                The Application Process
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                {processSteps.map((item) => (
                  <div key={item.step} className="text-center">
                    <div className="w-12 h-12 rounded-full bg-accent text-primary-foreground font-display font-bold text-xl flex items-center justify-center mx-auto mb-4">
                      {item.step}
                    </div>
                    <h3 className="font-semibold text-foreground mb-2">{item.title}</h3>
                    <p className="text-muted-foreground font-body text-sm">{item.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Eligibility */}
            <div className="max-w-3xl mx-auto mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                Eligibility Requirements
              </h2>
              <div className="bg-card rounded-2xl p-8 shadow-soft">
                <ul className="space-y-4">
                  {eligibility.map((item, index) => (
                    <li key={index} className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-accent text-primary-foreground font-bold text-sm flex items-center justify-center flex-shrink-0 mt-0.5">
                        ✓
                      </div>
                      <span className="text-muted-foreground font-body">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* FAQ */}
            <div className="max-w-3xl mx-auto mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                Frequently Asked Questions
              </h2>
              <div className="space-y-6">
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">What does a caretaker do?</h3>
                  <p className="text-muted-foreground font-body">Caretakers help maintain the property—basic upkeep like yard work, cleaning, and reporting any issues. BARN handles major repairs.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Is this a lease or rental agreement?</h3>
                  <p className="text-muted-foreground font-body">No, this is a Caretaker License. You're granted the right to live in the home while performing caretaking duties, not as a traditional tenant.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">How long can we stay?</h3>
                  <p className="text-muted-foreground font-body">The license continues as long as you fulfill your caretaking responsibilities. We work with each family to support their long-term housing goals.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Is there a cost to participate?</h3>
                  <p className="text-muted-foreground font-body">Our program is free for qualifying families. We may ask for a small contribution toward utilities once you're settled in.</p>
                </div>
              </div>
            </div>

            {/* Form Section */}
            <div className="max-w-2xl mx-auto text-center">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-4">
                Ready to Apply?
              </h2>
              <p className="text-muted-foreground font-body mb-8">
                Complete our housing application to start the process. Our team will review your application and reach out within 5-7 business days.
              </p>
              <Button variant="hero" size="xl" onClick={() => setFormOpen(true)}>
                Apply for Housing
              </Button>
            </div>
          </div>
        </section>
      </main>
      <Footer />
      <HousingApplicationForm open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
};

export default ApplyHousing;
