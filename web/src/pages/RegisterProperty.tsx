import { useState } from "react";
import { Shield, Wrench, Heart, ArrowLeft, Building } from "lucide-react";
import { Button } from "@/components/ui/button";
import * as reactRouterDom from "react-router-dom";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import OwnerRegistrationForm from "@/components/OwnerRegistrationForm";
import SavingsCalculator from "@/components/SavingsCalculator";

const benefits = [
  {
    icon: Shield,
    title: "No Tenant Complications",
    description: "Our Master Lease model means you never deal with tenant rights issues. Caretakers hold a revocable license—not a lease—so there are no eviction headaches.",
  },
  {
    icon: Wrench,
    title: "Zero Liability Maintenance",
    description: "BARN assumes full responsibility for all maintenance and code compliance. We keep your property in excellent condition at no cost to you.",
  },
  {
    icon: Heart,
    title: "Community Impact",
    description: "Your property helps families in need while staying protected. Our Caretaker Program provides housing stability without the risks of traditional rentals.",
  },
];

const processSteps = [
  {
    step: "1",
    title: "Initial Consultation",
    description: "We'll discuss your property, assess its condition, and explain our program in detail.",
  },
  {
    step: "2",
    title: "Property Assessment",
    description: "Our team inspects the property to determine renovation needs and timeline.",
  },
  {
    step: "3",
    title: "Renovation",
    description: "Volunteers and contractors work together to restore the property to livable condition.",
  },
  {
    step: "4",
    title: "Caretaker Placement",
    description: "We place a vetted caretaker under our license agreement—they maintain the property in exchange for housing.",
  },
];

const RegisterProperty = () => {
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-20">
        {/* Hero Section */}
        <section className="section-padding bg-primary text-primary-foreground">
          <div className="container-wide">
            <reactRouterDom.Link to="/#get-involved" className="inline-flex items-center gap-2 text-primary-foreground/80 hover:text-primary-foreground mb-6 transition-colors">
              <ArrowLeft size={18} />
              Back to Get Involved
            </reactRouterDom.Link>
            <div className="max-w-3xl">
              <div className="w-16 h-16 rounded-2xl bg-primary-foreground/20 flex items-center justify-center mb-6">
                <Building size={32} className="text-primary-foreground" />
              </div>
              <h1 className="font-display text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Register Your Property
              </h1>
              <p className="text-lg md:text-xl text-primary-foreground/90 font-body">
                Own a vacant or neglected property? Our Master Lease model protects you from tenant complications while putting your property to good use. BARN handles everything—no eviction worries, no maintenance hassles.
              </p>
            </div>
          </div>
        </section>

        {/* Benefits Section */}
        <section className="section-padding">
          <div className="container-wide">
            <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-12 text-center">
              Benefits for Property Owners
            </h2>
            <div className="grid md:grid-cols-3 gap-8 mb-16">
              {benefits.map((benefit) => (
                <div key={benefit.title} className="bg-card rounded-2xl p-8 shadow-soft">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                    <benefit.icon size={24} className="text-primary" />
                  </div>
                  <h3 className="font-display text-xl font-bold text-foreground mb-3">{benefit.title}</h3>
                  <p className="text-muted-foreground font-body">{benefit.description}</p>
                </div>
              ))}
            </div>

            {/* Process Steps */}
            <div className="bg-muted rounded-3xl p-8 md:p-12 mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                How the Process Works
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                {processSteps.map((item) => (
                  <div key={item.step} className="text-center">
                    <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground font-display font-bold text-xl flex items-center justify-center mx-auto mb-4">
                      {item.step}
                    </div>
                    <h3 className="font-semibold text-foreground mb-2">{item.title}</h3>
                    <p className="text-muted-foreground font-body text-sm">{item.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Savings Calculator Section */}
            <div className="max-w-3xl mx-auto mb-16">
              <SavingsCalculator />
            </div>

            {/* FAQ Section */}
            <div className="max-w-3xl mx-auto mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-8 text-center">
                Frequently Asked Questions
              </h2>
              <div className="space-y-6">
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">How does the Master Lease model work?</h3>
                  <p className="text-muted-foreground font-body">You sign a simple Use Agreement granting BARN property access for $1/year. We then place caretakers under a revocable license—not a lease. This protects you from tenant rights complications entirely.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">What if I need my property back?</h3>
                  <p className="text-muted-foreground font-body">Since caretakers hold a license (not a lease), there's no lengthy eviction process. We simply find them another property in the network where they are needed most.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Who handles maintenance and repairs?</h3>
                  <p className="text-muted-foreground font-body">BARN is fully responsible for all maintenance and code compliance. Caretakers help with upkeep as part of their agreement, and we coordinate any major repairs at no cost to you.</p>
                </div>
                <div className="bg-card rounded-xl p-6 shadow-soft">
                  <h3 className="font-semibold text-foreground mb-2">Do I retain ownership of my property?</h3>
                  <p className="text-muted-foreground font-body">Absolutely. You remain the legal owner at all times. The Master Lease simply grants BARN the right to use the property for our Caretaker Program.</p>
                </div>
              </div>
            </div>

            {/* Form Section */}
            <div className="max-w-2xl mx-auto text-center">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-4">
                Ready to Get Started?
              </h2>
              <p className="text-muted-foreground font-body mb-8">
                Fill out our registration form and a member of our team will contact you within 48 hours to discuss your property and answer any questions.
              </p>
              <Button variant="hero" size="xl" onClick={() => setFormOpen(true)}>
                Register Your Property
              </Button>
            </div>
          </div>
        </section>
      </main>
      <Footer />
      <OwnerRegistrationForm open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
};

export default RegisterProperty;
