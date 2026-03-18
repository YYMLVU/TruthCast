'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  FileSearch,
  History,
  LineChart,
  Home,
  Menu,
  X,
  FileText,
  MessageSquare,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from '@/components/ui/sheet';

const navItems = [
  { href: '/chat', label: '对话工作台', icon: MessageSquare },
  { href: '/', label: '任务输入', icon: Home },
  { href: '/result', label: '检测结果', icon: FileSearch },
  { href: '/simulation', label: '舆情预演', icon: LineChart },
  { href: '/content', label: '应对内容', icon: FileText },
  { href: '/history', label: '历史记录', icon: History },
];

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-lg supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center justify-between max-w-7xl px-4">
        <Link href="/" className="flex items-center space-x-2 shrink-0 group">
          <FileSearch className="h-6 w-6 text-primary transition-transform group-hover:scale-110" />
          <span className="font-bold text-primary">TruthCast</span>
        </Link>
        
        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-6 text-sm font-medium">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-1.5 transition-colors px-3 py-1.5 rounded-md text-sm font-medium',
                  isActive
                    ? 'text-primary bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        
        <div className="hidden md:block w-24 shrink-0" />
        
        {/* Mobile Menu */}
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild className="md:hidden">
            <Button variant="ghost" size="icon">
              <Menu className="h-5 w-5" />
              <span className="sr-only">打开菜单</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-[280px] pt-12 bg-background/95 backdrop-blur-lg">
            <SheetTitle className="sr-only">导航菜单</SheetTitle>
            <div className="flex items-center gap-2 mb-6 px-4">
              <FileSearch className="h-5 w-5 text-primary" />
              <span className="font-bold text-primary">TruthCast</span>
            </div>
            <nav className="flex flex-col space-y-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={isActive ? 'page' : undefined}
                    onClick={() => setOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-4 py-3 rounded-lg text-base font-medium transition-colors',
                      isActive
                        ? 'text-primary bg-primary/10'
                        : 'text-foreground/70 hover:bg-muted'
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
