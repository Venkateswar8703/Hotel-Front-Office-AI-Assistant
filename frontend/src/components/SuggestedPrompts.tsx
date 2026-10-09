
interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

const PROMPTS = [
  { text: 'What is the check-in & check-out policy?', icon: '🕐' },
  { text: 'What are the airport transfer rates & procedure?', icon: '✈️' },
  { text: 'Dispatch housekeeping: 2 extra towels to Room 405', icon: '🛁' },
  { text: 'Log maintenance: AC not working in Room 302', icon: '🔧' },
  { text: 'What is the pet policy and fee structure?', icon: '🐾' },
  { text: 'What are the breakfast hours and dining details?', icon: '🍽️' },
];

// ─── Suggested Prompts ────────────────────────────────────────────────────────

export function SuggestedPrompts({ onSelect, disabled }: SuggestedPromptsProps) {
  return (
    <div className="px-2 pb-3">
      <p className="text-xs text-hotel-muted font-medium mb-2.5 flex items-center gap-1.5">
        <span className="w-3 h-px bg-hotel-gold inline-block" />
        Front Desk Quick Actions & Queries
        <span className="w-3 h-px bg-hotel-gold inline-block" />
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {PROMPTS.map((p) => (
          <button
            key={p.text}
            onClick={() => onSelect(p.text)}
            disabled={disabled}
            className="text-left px-3.5 py-2.5 bg-white border border-stone-200 hover:border-hotel-gold hover:bg-amber-50/50 rounded-xl text-xs text-hotel-dark font-medium transition-all duration-150 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2.5 group shadow-sm"
          >
            <span className="text-lg leading-none group-hover:scale-110 transition-transform flex-shrink-0">
              {p.icon}
            </span>
            <span className="leading-snug">{p.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
