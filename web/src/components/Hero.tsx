import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import heroImage from "@/assets/bay-area-skyline.jpg";

const Hero = () => {
  const scrollToSection = (id: string) => {
    const element = document.querySelector(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
      {/* Background Image */}
      <div className="absolute inset-0 z-0">
        <img
          src={heroImage}
          alt="Aerial view of Oakland Bay Area neighborhoods"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-foreground/80 via-foreground/60 to-foreground/40" />
      </div>

      {/* Content */}
      <div className="relative z-10 container-wide px-6 lg:px-12 py-20">
        <div className="max-w-3xl">
          <span className="inline-block px-4 py-2 rounded-full bg-primary/20 text-primary-foreground text-sm font-medium mb-6 animate-fade-in backdrop-blur-sm border border-primary-foreground/20">
            Transforming Lives Through Housing
          </span>

          <h1 className="font-display text-4xl md:text-5xl lg:text-6xl xl:text-7xl font-bold text-primary-foreground leading-tight mb-6 opacity-0 animate-fade-in" style={{ animationDelay: '0.1s' }}>
            Renewing Homes.
            <br />
            <span className="text-barn-gold">Restoring Hope.</span>
          </h1>

          <p className="text-lg md:text-xl text-primary-foreground/90 max-w-xl mb-8 font-body opacity-0 animate-fade-in" style={{ animationDelay: '0.2s' }}>
            Our Caretaker Program connects vacant properties with families in need—creating stable housing while revitalizing Bay Area neighborhoods.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 opacity-0 animate-fade-in" style={{ animationDelay: '0.3s' }}>
            <Button variant="hero" size="xl" onClick={() => scrollToSection("#get-involved")}>
              Join Our Mission
              <ArrowRight className="ml-2" size={20} />
            </Button>
            <Button variant="heroOutline" size="xl" onClick={() => scrollToSection("#how-it-works")}>
              Learn How It Works
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
