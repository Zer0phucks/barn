import { useState } from "react";
import { MapPin, Search, Building, CheckCircle, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import PropertyReportForm from "@/components/PropertyReportForm";

const benefits = [
  {
    icon: Search,
    title: "Help Us Identify Properties",
    description: "Your local knowledge is invaluable. You might know about abandoned homes in your neighborhood that we haven't discovered yet.",
  },
  {
    icon: Building,
    title: "Transform Blight into Housing",
    description: "Every reported property is a potential home for a family in need. Your report could be the first step in someone's journey to stable housing.",
  },
  {
    icon: CheckCircle,
    title: "Improve Your Community",
    description: "Abandoned properties can attract crime and reduce property values. Helping us find them benefits the entire neighborhood.",
  },
];

const ReportProperty = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-20">
        {/* Hero Section */}
        <section className="section-padding bg-primary text-primary-foreground">
          <div className="container-wide">
            <Link to="/#get-involved" className="inline-flex items-center gap-2 text-primary-foreground/80 hover:text-primary-foreground mb-6 transition-colors">
              <ArrowLeft size={18} />
              Back to Get Involved
            </Link>
            <div className="max-w-3xl">
              <div className="w-16 h-16 rounded-2xl bg-primary-foreground/20 flex items-center justify-center mb-6">
                <MapPin size={32} className="text-primary-foreground" />
              </div>
              <h1 className="font-display text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Report an Abandoned Property
              </h1>
              <p className="text-lg md:text-xl text-primary-foreground/90 font-body">
                Help us identify abandoned or neglected properties in the Bay Area. Your report could be the first step in transforming a forgotten building into a family's new home.
              </p>
            </div>
          </div>
        </section>

        {/* Benefits Section */}
        <section className="section-padding">
          <div className="container-wide">
            <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-12 text-center">
              Why Report a Property?
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

            {/* What We Look For */}
            <div className="bg-muted rounded-3xl p-8 md:p-12 mb-16">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-6">
                What We Look For
              </h2>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-semibold text-foreground mb-2">Signs of Abandonment</h3>
                  <ul className="space-y-2 text-muted-foreground font-body">
                    <li>• Overgrown vegetation or neglected landscaping</li>
                    <li>• Boarded-up windows or doors</li>
                    <li>• Accumulated mail or debris</li>
                    <li>• Visible structural damage</li>
                  </ul>
                </div>
                <div>
                  <h3 className="font-semibold text-foreground mb-2">Property Types</h3>
                  <ul className="space-y-2 text-muted-foreground font-body">
                    <li>• Single-family homes</li>
                    <li>• Duplexes and small multi-family buildings</li>
                    <li>• Vacant lots with existing structures</li>
                    <li>• Properties in any Bay Area city</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Form Section */}
            <div className="max-w-2xl mx-auto text-center">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-foreground mb-4">
                Ready to Submit a Report?
              </h2>
              <p className="text-muted-foreground font-body mb-8">
                Fill out our simple form with the property address and any additional details you can provide. Your contact information is optional but helps us follow up if needed.
              </p>
              <PropertyReportForm
                trigger={
                  <Button variant="hero" size="xl">
                    Report a Property
                  </Button>
                }
              />
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
};

export default ReportProperty;
