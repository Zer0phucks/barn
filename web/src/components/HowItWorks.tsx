import { Search, Handshake, Home, Wrench } from "lucide-react";

const steps = [
  {
    icon: Search,
    title: "Identify Properties",
    description: "Our volunteer scouts identify abandoned and neglected properties throughout the Bay Area that have potential for renewal.",
    color: "bg-barn-red-light text-barn-red",
  },
  {
    icon: Handshake,
    title: "Partner with Owners",
    description: "We reach out to property owners, presenting a win-win opportunity: free maintenance in exchange for housing a family in need.",
    color: "bg-barn-green-light text-barn-green",
  },
  {
    icon: Wrench,
    title: "Restore & Renovate",
    description: "Our skilled volunteer crews bring properties up to code, making them safe, clean, and welcoming homes.",
    color: "bg-barn-gold-light text-barn-gold",
  },
  {
    icon: Home,
    title: "Welcome Home",
    description: "We match carefully vetted families with renewed properties, providing ongoing support for sustainable housing.",
    color: "bg-barn-blue-light text-barn-blue",
  },
];

const HowItWorks = () => {
  return (
    <section id="how-it-works" className="section-padding bg-gradient-warm">
      <div className="container-wide">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <span className="text-primary font-medium text-sm uppercase tracking-wider">Our Process</span>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mt-4 mb-6">
            How We Create <span className="text-gradient">Change</span>
          </h2>
          <p className="text-muted-foreground text-lg font-body">
            Through community collaboration, we transform abandoned properties into safe, 
            welcoming homes while giving families a fresh start.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, index) => (
            <div
              key={step.title}
              className="group relative"
            >
              {/* Connector Line */}
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-12 left-1/2 w-full h-0.5 bg-border" />
              )}
              
              <div className="relative bg-card rounded-2xl p-8 shadow-soft hover:shadow-elevated transition-all duration-300 h-full">
                {/* Step Number */}
                <span className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                  {index + 1}
                </span>
                
                {/* Icon */}
                <div className={`w-16 h-16 rounded-2xl ${step.color} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300`}>
                  <step.icon size={28} />
                </div>
                
                <h3 className="font-display text-xl font-semibold text-foreground mb-3">
                  {step.title}
                </h3>
                <p className="text-muted-foreground font-body">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
