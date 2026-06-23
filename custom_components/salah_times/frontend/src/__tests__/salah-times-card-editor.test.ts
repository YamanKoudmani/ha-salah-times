import { describe, it, expect, vi, afterEach } from 'vitest';
import '../salah-times-card-editor.js';
import type { SalahTimesCardEditor } from '../salah-times-card-editor.js';
import type { HassLike } from '../types.js';

/**
 * HA provides <ha-form> at runtime. For unit tests we register a stub
 * so the editor's render() doesn't crash trying to create an undefined element.
 */
class HaFormStub extends HTMLElement {
  hass: unknown;
  data: unknown;
  schema: unknown;
}
if (!customElements.get('ha-form')) {
  customElements.define('ha-form', HaFormStub);
}

const MOCK_HASS: HassLike = {
  states: {},
  config: { time_zone: 'UTC' },
  locale: { language: 'en' },
};

describe('salah-times-card-editor', () => {
  let editor: SalahTimesCardEditor;

  afterEach(() => {
    if (editor && editor.parentNode) {
      editor.parentNode.removeChild(editor);
    }
  });

  /* ── Render conditions ── */

  it('renders the ha-form when both hass and config are set', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.hass = MOCK_HASS;
    editor.setConfig({ show_hijri: true });
    document.body.appendChild(editor);
    await editor.updateComplete;
    const form = editor.shadowRoot!.querySelector('ha-form');
    expect(form).toBeTruthy();
  });

  it('renders nothing when hass is missing', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.setConfig({ show_hijri: true });
    document.body.appendChild(editor);
    await editor.updateComplete;
    const form = editor.shadowRoot!.querySelector('ha-form');
    expect(form).toBeFalsy();
  });

  it('renders nothing when config is missing', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.hass = MOCK_HASS;
    document.body.appendChild(editor);
    await editor.updateComplete;
    const form = editor.shadowRoot!.querySelector('ha-form');
    expect(form).toBeFalsy();
  });

  /* ── setConfig ── */

  it('stores config via setConfig', () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.setConfig({ show_hijri: false });
    expect(editor['_config']).toEqual({ show_hijri: false });
  });

  /* ── Event dispatch ── */

  it('value-changed on form dispatches config-changed with new config', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.hass = MOCK_HASS;
    editor.setConfig({ show_hijri: true });
    document.body.appendChild(editor);
    await editor.updateComplete;

    const handler = vi.fn();
    editor.addEventListener('config-changed', handler);

    const form = editor.shadowRoot!.querySelector('ha-form') as HaFormStub;
    const newValue = { show_hijri: false };
    form.dispatchEvent(
      new CustomEvent('value-changed', { detail: { value: newValue } }),
    );

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: { config: { show_hijri: false } },
      }),
    );
  });

  it('dispatched config-changed event has bubbles:true and composed:true', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.hass = MOCK_HASS;
    editor.setConfig({ show_hijri: true });
    document.body.appendChild(editor);
    await editor.updateComplete;

    const handler = vi.fn();
    editor.addEventListener('config-changed', handler);

    const form = editor.shadowRoot!.querySelector('ha-form') as HaFormStub;
    form.dispatchEvent(
      new CustomEvent('value-changed', {
        detail: { value: { show_hijri: false } },
      }),
    );

    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.bubbles).toBe(true);
    expect(event.composed).toBe(true);
  });

  /* ── Schema labels and descriptions ── */

  it('schema includes human-readable labels and descriptions for all fields', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.hass = MOCK_HASS;
    editor.setConfig({ show_hijri: true });
    document.body.appendChild(editor);
    await editor.updateComplete;

    const form = editor.shadowRoot!.querySelector('ha-form') as HaFormStub;
    const schema = form.schema as any[];

    expect(schema).toBeTruthy();
    expect(schema.length).toBeGreaterThan(0);

    for (const field of schema) {
      expect(field).toHaveProperty('name');
      expect(field).toHaveProperty('label');
      expect(field).toHaveProperty('description');
      expect(typeof field.label).toBe('string');
      expect(field.label.length).toBeGreaterThan(0);
      expect(typeof field.description).toBe('string');
      expect(field.description.length).toBeGreaterThan(0);
    }
  });

  it('show_method has a description explaining its dependency on show_hijri', async () => {
    editor = document.createElement('salah-times-card-editor') as SalahTimesCardEditor;
    editor.hass = MOCK_HASS;
    editor.setConfig({ show_hijri: true });
    document.body.appendChild(editor);
    await editor.updateComplete;

    const form = editor.shadowRoot!.querySelector('ha-form') as HaFormStub;
    const schema = form.schema as any[];

    const showMethod = schema.find((f: any) => f.name === 'show_method');
    expect(showMethod).toBeTruthy();
    expect(showMethod.description.toLowerCase()).toContain('show hijri date');
  });
});
