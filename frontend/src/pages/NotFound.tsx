import { useLocation, Link } from "react-router-dom";
import { useEffect } from "react";
import { logger } from '@/lib/logger';
import { Salad } from 'lucide-react';
import { Button } from '@/components/ui/button';

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    logger.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center gradient-bg">
      <div className="text-center">
        <div className="flex justify-center mb-6">
          <div className="h-14 w-14 rounded-full gradient-green flex items-center justify-center glow-green opacity-50">
            <Salad className="h-7 w-7 text-white" />
          </div>
        </div>
        <h1 className="text-6xl font-bold text-foreground mb-2">404</h1>
        <p className="text-lg text-muted-foreground mb-6">Page introuvable</p>
        <Button asChild className="gradient-green text-white">
          <Link to="/">Retour à l'accueil</Link>
        </Button>
      </div>
    </div>
  );
};

export default NotFound;
