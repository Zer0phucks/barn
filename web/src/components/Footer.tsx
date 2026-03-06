import { Heart } from "lucide-react";
import { Link } from "react-router-dom";
import barnLogo from "@/assets/barn-logo.png";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  const footerLinks = {
    "Get Involved": [
      { label: "Report a Property", href: "/report-property" },
      { label: "Register Your Property", href: "/register-property" },
      { label: "Volunteer", href: "/volunteer" },
      { label: "Apply for Housing", href: "/apply-housing" },
    ],
    "About Us": [
      { label: "Our Mission", href: "/#about" },
      { label: "How It Works", href: "/#how-it-works" },
      { label: "Contact", href: "/#contact" },
    ],
  };

  return (
    <footer className="bg-card border-t border-border">
      <div className="container-wide px-6 lg:px-12 py-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-12">
          {/* Brand */}
          <div className="lg:col-span-2">
            <a href="#" className="flex items-center gap-3 mb-6">
              <img src={barnLogo} alt="BARN Logo" className="w-14 h-14 object-contain" />
              <div>
                <span className="font-display font-semibold text-xl text-foreground">Bay Area</span>
                <span className="font-display font-semibold text-xl text-primary ml-1">Renewal Network</span>
              </div>
            </a>
            <p className="text-muted-foreground font-body mb-6 max-w-sm">
              Transforming abandoned properties into homes and giving families the stability 
              they need to thrive. Together, we're renewing the Bay Area.
            </p>
            <p className="text-sm text-muted-foreground">
              Bay Area Renewal Network is a community-based housing organization 
              dedicated to renewing neighborhoods and restoring hope.
            </p>
          </div>

          {/* Links */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h4 className="font-display font-semibold text-foreground mb-4">{category}</h4>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link
                      to={link.href}
                      className="text-muted-foreground hover:text-foreground transition-colors font-body"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <div className="mt-16 pt-8 border-t border-border flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-muted-foreground text-sm flex items-center gap-1">
            © {currentYear} Bay Area Renewal Network. Made with <Heart size={14} className="text-primary" /> in Oakland, CA.
          </p>
          <div className="flex gap-6 text-sm">
            <Link to="/admin" className="text-muted-foreground hover:text-foreground transition-colors">
              Admin
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
