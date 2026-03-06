import { Menu, X, ChevronDown } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import barnLogo from "@/assets/barn-logo.png";

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const isHomePage = location.pathname === "/";

  const handleHashLink = (hash: string) => {
    if (isHomePage) {
      const element = document.querySelector(hash);
      if (element) {
        element.scrollIntoView({ behavior: "smooth" });
      }
    } else {
      navigate("/" + hash);
    }
    setIsMenuOpen(false);
  };

  const mainNavLinks = [
    { label: "Home", href: "/" },
    { label: "How It Works", hash: "#how-it-works" },
    { label: "About", hash: "#about" },
  ];

  const getInvolvedLinks = [
    { label: "Report a Property", href: "/report-property" },
    { label: "Register Your Property", href: "/register-property" },
    { label: "Volunteer", href: "/volunteer" },
    { label: "Apply for Housing", href: "/apply-housing" },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="container-wide px-6 lg:px-12">
        <nav className="flex items-center justify-between h-16 lg:h-20">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3">
            <img src={barnLogo} alt="BARN - Bay Area Renewal Network" className="h-14 lg:h-16 object-contain" />
            <span className="font-display font-semibold text-lg lg:text-xl text-foreground leading-tight">
              Bay Area<br />
              <span className="text-primary">Renewal Network</span>
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center gap-6">
            {mainNavLinks.map((link) =>
              link.href ? (
                <Link
                  key={link.label}
                  to={link.href}
                  className="text-muted-foreground hover:text-foreground transition-colors font-body font-medium"
                >
                  {link.label}
                </Link>
              ) : (
                <button
                  key={link.label}
                  onClick={() => handleHashLink(link.hash!)}
                  className="text-muted-foreground hover:text-foreground transition-colors font-body font-medium"
                >
                  {link.label}
                </button>
              )
            )}

            {/* Get Involved Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors font-body font-medium">
                Get Involved
                <ChevronDown size={16} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="center" className="w-48">
                {getInvolvedLinks.map((link) => (
                  <DropdownMenuItem key={link.label} asChild>
                    <Link to={link.href} className="cursor-pointer">
                      {link.label}
                    </Link>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <button
              onClick={() => handleHashLink("#contact")}
              className="text-muted-foreground hover:text-foreground transition-colors font-body font-medium"
            >
              Contact
            </button>
          </div>

          {/* CTA Button */}
          <div className="hidden lg:flex items-center gap-4">
            <Button variant="hero" size="default" onClick={() => handleHashLink("#donate")}>
              Donate Now
            </Button>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="lg:hidden p-2 text-foreground"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-label="Toggle menu"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </nav>

        {/* Mobile Menu */}
        {isMenuOpen && (
          <div className="lg:hidden py-6 border-t border-border animate-fade-in">
            <div className="flex flex-col gap-4">
              <Link
                to="/"
                className="text-foreground font-body font-medium py-2"
                onClick={() => setIsMenuOpen(false)}
              >
                Home
              </Link>
              <button
                onClick={() => handleHashLink("#how-it-works")}
                className="text-foreground font-body font-medium py-2 text-left"
              >
                How It Works
              </button>
              <button
                onClick={() => handleHashLink("#about")}
                className="text-foreground font-body font-medium py-2 text-left"
              >
                About
              </button>

              {/* Mobile Get Involved Section */}
              <div className="border-t border-border pt-4 mt-2">
                <span className="text-sm text-muted-foreground font-medium mb-2 block">Get Involved</span>
                {getInvolvedLinks.map((link) => (
                  <Link
                    key={link.label}
                    to={link.href}
                    className="text-foreground font-body font-medium py-2 pl-4 block"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    {link.label}
                  </Link>
                ))}
              </div>

              <button
                onClick={() => handleHashLink("#contact")}
                className="text-foreground font-body font-medium py-2 text-left"
              >
                Contact
              </button>

              <Button variant="hero" size="lg" className="mt-4 w-full" onClick={() => handleHashLink("#donate")}>
                Donate Now
              </Button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;

