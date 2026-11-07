/**
 * AquaSentry — Restrained Web Audio Sound Feedback Engine (Items 375–381)
 *
 * Design Guidelines:
 * - OFF BY DEFAULT on first launch (requires explicit user opt-in).
 * - Gentle, low-volume, non-alarming sound set using Web Audio API synthesis.
 * - Categories: Action confirmation, sample receipt, high-priority alert.
 * - Pauses when browser tab is hidden; safe on file:// and headless environments.
 * - Never plays on hover, continuous stream updates, or ordinary navigation.
 */

(function () {
  'use strict';

  let audioCtx = null;
  // OFF BY DEFAULT: requires explicit 'true' in localStorage
  let isAudioEnabled = localStorage.getItem('aquaSentryAudioEnabled') === 'true';
  let masterVolume = parseFloat(localStorage.getItem('aquaSentryAudioVolume') || '0.25');

  // Per-category preferences
  let settings = {
    confirmation: localStorage.getItem('aquaSentrySound_confirmation') !== 'false',
    sample: localStorage.getItem('aquaSentrySound_sample') !== 'false',
    alert: localStorage.getItem('aquaSentrySound_alert') !== 'false',
  };

  function getAudioContext() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtx = new AudioContext();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {});
    }
    return audioCtx;
  }

  // Auto-pause when tab is hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && audioCtx && audioCtx.state === 'running') {
      audioCtx.suspend().catch(() => {});
    }
  });

  window.AquaAudio = {
    isEnabled: function () {
      return isAudioEnabled;
    },

    toggleAudio: function () {
      isAudioEnabled = !isAudioEnabled;
      localStorage.setItem('aquaSentryAudioEnabled', String(isAudioEnabled));
      this.updateUI();
      if (isAudioEnabled) {
        this.playConfirmation();
      }
      return isAudioEnabled;
    },

    setVolume: function (vol) {
      masterVolume = Math.max(0.0, Math.min(1.0, parseFloat(vol)));
      localStorage.setItem('aquaSentryAudioVolume', String(masterVolume));
    },

    getVolume: function () {
      return masterVolume;
    },

    updateUI: function () {
      const btn = document.getElementById('audioToggleBtn');
      if (btn) {
        btn.innerHTML = isAudioEnabled
          ? `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M11 5L6 9H2v6h4l5 4V5z"></path><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg><span>Audio: ON</span>`
          : `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M11 5L6 9H2v6h4l5 4V5z"></path><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg><span>Audio: OFF</span>`;
        btn.classList.toggle('audio-active', isAudioEnabled);
        btn.classList.toggle('audio-muted', !isAudioEnabled);
        btn.setAttribute('aria-pressed', String(isAudioEnabled));
      }
    },

    // Soft 60ms confirmation tone (440Hz -> 520Hz)
    playConfirmation: function () {
      if (!isAudioEnabled || !settings.confirmation || document.hidden) return;
      const ctx = getAudioContext();
      if (!ctx) return;

      try {
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(520, now + 0.06);

        gain.gain.setValueAtTime(0.04 * masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.06);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.06);
      } catch (e) {
        // Safe silent fallback
      }
    },

    // Soft two-note acknowledgement for live sample arrival (520Hz -> 660Hz)
    playSampleTone: function () {
      if (!isAudioEnabled || !settings.sample || document.hidden) return;
      const ctx = getAudioContext();
      if (!ctx) return;

      try {
        const now = ctx.currentTime;
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gain = ctx.createGain();

        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(520, now);
        osc1.frequency.setValueAtTime(660, now + 0.08);

        gain.gain.setValueAtTime(0.05 * masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);

        osc1.connect(gain);
        gain.connect(ctx.destination);

        osc1.start(now);
        osc1.stop(now + 0.22);
      } catch (e) {}
    },

    // Non-alarming, distinct double alert tone (360Hz -> 280Hz)
    playAlertTone: function () {
      if (!isAudioEnabled || !settings.alert || document.hidden) return;
      const ctx = getAudioContext();
      if (!ctx) return;

      try {
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(360, now);
        osc.frequency.setValueAtTime(280, now + 0.12);

        gain.gain.setValueAtTime(0.06 * masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.28);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.28);
      } catch (e) {}
    },

    // Sound preview helper
    previewSound: function (type) {
      const prev = isAudioEnabled;
      isAudioEnabled = true;
      if (type === 'confirmation') this.playConfirmation();
      else if (type === 'sample') this.playSampleTone();
      else if (type === 'alert') this.playAlertTone();
      isAudioEnabled = prev;
    },
  };

  // Sync UI on DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    window.AquaAudio.updateUI();
  });
})();
