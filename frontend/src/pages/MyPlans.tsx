import { BookOpen } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-mobile';
import { MobileHeader } from '@/components/navigation/MobileHeader';

const MyPlans = () => {
  const isMobile = useIsMobile();

  return (
    <div className="flex flex-col h-screen gradient-bg">
      {isMobile && <MobileHeader title="Mes Plans" />}
      {!isMobile && (
        <div className="flex items-center h-14 border-b border-border/50 px-6">
          <h1 className="text-lg font-semibold">Mes Plans</h1>
        </div>
      )}
      <div className={`flex-1 flex flex-col items-center justify-center gap-4 ${isMobile ? 'pb-14' : ''}`}>
        <BookOpen className="h-16 w-16 text-muted-foreground/50" />
        <h2 className="text-xl font-semibold text-muted-foreground">Mes Plans</h2>
        <p className="text-muted-foreground/70 text-sm">Bientôt disponible</p>
      </div>
    </div>
  );
};

export default MyPlans;
