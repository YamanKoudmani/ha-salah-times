import { describe, it, expect, vi, afterEach } from 'vitest';
import '../salah-times-cell.js';
import type { SalahTimesCell } from '../salah-times-cell.js';

/**
 * Helper: create a <salah-times-cell> in a detached container,
 * set properties, wait for update, and return the element.
 */
async function createCell(
  overrides: Partial<{
    name: string;
    time: string;
    icon: string;
    state: 'past' | 'next' | 'future';
    entityId: string | null;
    compact: boolean;
  }> = {},
): Promise<SalahTimesCell> {
  const el = document.createElement('salah-times-cell') as SalahTimesCell;
  el.name = overrides.name ?? 'Fajr';
  el.time = overrides.time ?? '4:11 AM';
  el.icon = overrides.icon ?? 'mdi:weather-sunset-up';
  el.state = overrides.state ?? 'future';
  el.entityId = overrides.entityId ?? null;
  if (overrides.compact) el.compact = true;
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe('salah-times-cell', () => {
  let cell: SalahTimesCell;

  afterEach(() => {
    if (cell && cell.parentNode) {
      cell.parentNode.removeChild(cell);
    }
  });

  /* ── Rendering (via shadow DOM + attributes) ── */

  it('renders name, time, and icon in shadow DOM', async () => {
    cell = await createCell({
      name: 'Maghrib',
      time: '8:39 PM',
      icon: 'mdi:weather-sunset-down',
    });
    const root = cell.shadowRoot;
    expect(root).toBeTruthy();

    // Check that the name and time appear in the shadow DOM
    expect(root!.textContent).toContain('Maghrib');
    expect(root!.textContent).toContain('8:39 PM');

    // Check for ha-icon element
    const iconEl = root!.querySelector('ha-icon');
    expect(iconEl).toBeTruthy();
    expect(iconEl!.getAttribute('icon')).toBe('mdi:weather-sunset-down');
  });

  /* ── State classes ── */

  it('renders with cell--future class by default', async () => {
    cell = await createCell();
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.classList.contains('future')).toBe(true);
    expect(inner.classList.contains('past')).toBe(false);
    expect(inner.classList.contains('next')).toBe(false);
  });

  it('renders with cell--past class when state="past"', async () => {
    cell = await createCell({ state: 'past' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.classList.contains('past')).toBe(true);
  });

  it('renders with cell--next class when state="next"', async () => {
    cell = await createCell({ state: 'next' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.classList.contains('next')).toBe(true);
  });

  /* ── ARIA attributes ── */

  it('has role="button"', async () => {
    cell = await createCell();
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('role')).toBe('button');
  });

  it('has aria-label with state suffix for future', async () => {
    cell = await createCell({ name: 'Fajr', time: '4:11 AM', state: 'future' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('aria-label')).toBe('Fajr at 4:11 AM, upcoming');
  });

  it('has aria-label with state suffix for past', async () => {
    cell = await createCell({ name: 'Isha', time: '10:15 PM', state: 'past' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('aria-label')).toBe('Isha at 10:15 PM, past');
  });

  it('has aria-label with state suffix for next', async () => {
    cell = await createCell({ name: 'Maghrib', time: '8:39 PM', state: 'next' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('aria-label')).toBe('Maghrib at 8:39 PM, next prayer');
  });

  it('has aria-current="true" when state="next"', async () => {
    cell = await createCell({ state: 'next' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('aria-current')).toBe('true');
  });

  it('has no aria-current attribute when state is not next', async () => {
    cell = await createCell({ state: 'future' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.hasAttribute('aria-current')).toBe(false);
  });

  /* ── Tabindex / tappable ── */

  it('tabindex="0" when entityId is set', async () => {
    cell = await createCell({ entityId: 'sensor.home_fajr' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('tabindex')).toBe('0');
  });

  it('tabindex="-1" when entityId is null', async () => {
    cell = await createCell({ entityId: null });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.getAttribute('tabindex')).toBe('-1');
  });

  it('has .tappable class when entityId set', async () => {
    cell = await createCell({ entityId: 'sensor.home_fajr' });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.classList.contains('tappable')).toBe(true);
  });

  it('lacks .tappable class when entityId is null', async () => {
    cell = await createCell({ entityId: null });
    const inner = cell.shadowRoot!.querySelector('.cell')!;
    expect(inner.classList.contains('tappable')).toBe(false);
  });

  /* ── Event dispatching ── */

  it('click with entityId dispatches hass-more-info with correct entityId', async () => {
    cell = await createCell({ entityId: 'sensor.home_maghrib' });
    const handler = vi.fn();
    cell.addEventListener('hass-more-info', handler);
    const inner = cell.shadowRoot!.querySelector('.cell')! as HTMLElement;
    inner.click();
    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.detail.entityId).toBe('sensor.home_maghrib');
    expect(event.bubbles).toBe(true);
    expect(event.composed).toBe(true);
    cell.removeEventListener('hass-more-info', handler);
  });

  it('click without entityId does NOT dispatch', async () => {
    cell = await createCell({ entityId: null });
    const handler = vi.fn();
    cell.addEventListener('hass-more-info', handler);
    const inner = cell.shadowRoot!.querySelector('.cell')! as HTMLElement;
    inner.click();
    expect(handler).not.toHaveBeenCalled();
    cell.removeEventListener('hass-more-info', handler);
  });

  it('Enter key on tappable cell dispatches', async () => {
    cell = await createCell({ entityId: 'sensor.home_fajr' });
    const handler = vi.fn();
    cell.addEventListener('hass-more-info', handler);
    const inner = cell.shadowRoot!.querySelector('.cell')! as HTMLElement;
    inner.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(handler).toHaveBeenCalledTimes(1);
    cell.removeEventListener('hass-more-info', handler);
  });

  it('Space key on tappable cell dispatches', async () => {
    cell = await createCell({ entityId: 'sensor.home_fajr' });
    const handler = vi.fn();
    cell.addEventListener('hass-more-info', handler);
    const inner = cell.shadowRoot!.querySelector('.cell')! as HTMLElement;
    inner.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    expect(handler).toHaveBeenCalledTimes(1);
    cell.removeEventListener('hass-more-info', handler);
  });

  it('Enter key on non-tappable cell does NOT dispatch', async () => {
    cell = await createCell({ entityId: null });
    const handler = vi.fn();
    cell.addEventListener('hass-more-info', handler);
    const inner = cell.shadowRoot!.querySelector('.cell')! as HTMLElement;
    inner.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(handler).not.toHaveBeenCalled();
    cell.removeEventListener('hass-more-info', handler);
  });

  /* ── Time text layout ── */

  it('renders time without wrapping (white-space: nowrap applied)', async () => {
    cell = await createCell({ time: '10:13 PM' });
    const timeEl = cell.shadowRoot!.querySelector('.cell__time') as HTMLElement;
    expect(timeEl).toBeTruthy();
    // jsdom getComputedStyle doesn't resolve styles from constructible
    // stylesheets. Verify via the shadow root's style rules instead.
    const sheets = cell.shadowRoot!.adoptedStyleSheets;
    if (sheets && sheets.length > 0) {
      // Modern Lit with adoptedStyleSheets
      const rules = sheets.flatMap((s: any) => Array.from(s.cssRules));
      const hasNowrap = rules.some((r: any) =>
        r.cssText?.includes('.cell__time') && r.cssText?.includes('white-space: nowrap'),
      );
      expect(hasNowrap).toBe(true);
    } else {
      // Fallback: find <style> element in shadow root
      const styleEl = cell.shadowRoot!.querySelector('style');
      const cssText = styleEl?.textContent ?? '';
      // Compressed form: Lit may strip spaces
      const normalized = cssText.replace(/\s+/g, ' ');
      expect(normalized).toContain('.cell__time');
      expect(normalized).toContain('white-space: nowrap');
    }
    // Verify the rendered text stays on one line (no wrapping marker)
    expect(timeEl.textContent).toBe('10:13 PM');
  });
});
