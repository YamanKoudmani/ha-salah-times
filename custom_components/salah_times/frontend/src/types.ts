export interface SalahTimesConfig {
  entity?: string;
  show_hijri?: boolean;
  show_method?: boolean;
  show_countdown?: boolean;
  time_format?: 'auto' | '12' | '24';
  accent_color?: string | null;
  compact?: boolean;
  optional_prayers?: ('sunrise' | 'imsak' | 'midnight')[];
}

export interface SalahTimesCellProps {
  name: string;
  time: string;
  icon: string;
  state: 'past' | 'next' | 'future';
  entityId: string | null;
  compact: boolean;
}

export interface HassLike {
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  config: {
    time_zone?: string;
  };
  locale?: {
    language?: string;
  };
  localize?: (key: string, ...args: unknown[]) => string;
}
