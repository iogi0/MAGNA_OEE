import React from 'react';
import { Bell, Settings, User, Activity, Sparkles, ChevronRight, CheckCircle2 } from 'lucide-react';

interface Props {
  activeTab: 'shift' | 'weekly' | 'monthly' | 'machine';
  setActiveTab: (tab: 'shift' | 'weekly' | 'monthly' | 'machine') => void;
  hasAlarms?: boolean;
}

export const HeaderNav: React.FC<Props> = ({
  activeTab,
  setActiveTab,
  hasAlarms = true,
}) => {
  return (
    <header className="max-w-[1440px] w-full mx-auto px-6 py-6 flex flex-col md:flex-row items-center justify-between gap-5 select-none">
      
      {/* 1. Left: Brand & Line Identification */}
      <div className="flex items-center gap-3.5">
        <div className="w-10 h-10 rounded-2xl bg-[#111827] flex items-center justify-center text-white shadow-md">
          <Activity className="w-5 h-5 text-[#3B82F6]" />
        </div>
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-[#111827]">
              Magna OEE
            </h1>
            <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#3B82F6]/10 text-[#3B82F6] border border-[#3B82F6]/20 uppercase tracking-wider">
              Linka L01
            </span>
          </div>
          <p className="text-xs text-[#6B7280]">
            Montáž elektrických pohonov • Systém riadenia OEE
          </p>
        </div>
      </div>

      {/* 2. Center: Pill Navigation Menu (CityCare Exact Style) */}
      <nav className="flex items-center p-1.5 bg-[#E5E7EB]/70 backdrop-blur-md rounded-full border border-white/80 shadow-inner">
        <button
          onClick={() => setActiveTab('shift')}
          className={`px-5 py-2 text-xs font-semibold rounded-full transition-all duration-200 ${
            activeTab === 'shift'
              ? 'bg-[#111827] text-white shadow-md'
              : 'text-[#6B7280] hover:text-[#111827] hover:bg-black/5'
          }`}
        >
          Dashboard (8h zmena)
        </button>

        <button
          onClick={() => setActiveTab('weekly')}
          className={`px-5 py-2 text-xs font-semibold rounded-full transition-all duration-200 ${
            activeTab === 'weekly'
              ? 'bg-[#111827] text-white shadow-md'
              : 'text-[#6B7280] hover:text-[#111827] hover:bg-black/5'
          }`}
        >
          Týždenný prehľad (7 dní)
        </button>

        <button
          onClick={() => setActiveTab('monthly')}
          className={`px-5 py-2 text-xs font-semibold rounded-full transition-all duration-200 ${
            activeTab === 'monthly'
              ? 'bg-[#111827] text-white shadow-md'
              : 'text-[#6B7280] hover:text-[#111827] hover:bg-black/5'
          }`}
        >
          Mesačný prehľad (30 dní)
        </button>

        <button
          onClick={() => setActiveTab('machine')}
          className={`px-5 py-2 text-xs font-semibold rounded-full transition-all duration-200 flex items-center gap-1.5 ${
            activeTab === 'machine'
              ? 'bg-[#111827] text-white shadow-md'
              : 'text-[#6B7280] hover:text-[#111827] hover:bg-black/5'
          }`}
        >
          <span>Factory X-Ray</span>
          {hasAlarms && (
            <span className="w-2 h-2 rounded-full bg-[#EF4444] animate-pulse" />
          )}
        </button>
      </nav>

      {/* 3. Right: Utility Controls & User Avatar Profile */}
      <div className="flex items-center gap-3">
        {/* Notification Bell */}
        <button 
          title="Upozornenia linky" 
          className="relative p-2.5 rounded-full bg-white border border-gray-200/80 text-[#6B7280] hover:text-[#111827] hover:bg-gray-50 transition-colors shadow-sm"
        >
          <Bell className="w-4 h-4" />
          {hasAlarms && (
            <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-[#EF4444] ring-2 ring-white" />
          )}
        </button>

        {/* Settings */}
        <button 
          title="Nastavenia normy (CT = 60s)"
          className="p-2.5 rounded-full bg-white border border-gray-200/80 text-[#6B7280] hover:text-[#111827] hover:bg-gray-50 transition-colors shadow-sm"
        >
          <Settings className="w-4 h-4" />
        </button>

        {/* User Avatar */}
        <div className="flex items-center gap-2.5 pl-2">
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#111827] to-[#3B82F6] flex items-center justify-center text-white font-bold text-xs ring-2 ring-white shadow-sm">
              PK
            </div>
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-[#10B981] ring-2 ring-white" />
          </div>
          <div className="hidden xl:block text-left">
            <div className="text-xs font-bold text-[#111827]">Peter Kováč</div>
            <div className="text-[10px] text-[#6B7280]">Zmenový inžinier</div>
          </div>
        </div>
      </div>

    </header>
  );
};
