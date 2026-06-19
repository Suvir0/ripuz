import React, { useState } from 'react';
import { SectionHead } from '../../components/SectionHead/SectionHead';
import { InfoCard } from '../../components/InfoCard/InfoCard';
import { Card } from '../../components/Card/Card';
import { Field } from '../../components/Field/Field';
import { Button, ButtonRow } from '../../components/Button/Button';
import { Msg } from '../../components/Msg/Msg';
import { Checkbox } from '../../components/Checkbox/Checkbox';

export interface Settings {
  qobuz_token?: string;
  downloads_dir?: string;
  music_dir?: string;
  music_quality?: number;
  download_lyrics?: boolean;
  prefer_explicit?: boolean;
  notify_webhook_url?: string;
}

export interface SettingsScreenProps {
  settings?: Settings;
  tokenSaved?: boolean;
  onSave?: (settings: Partial<Settings> & { qobuz_token?: string }) => void;
  msgText?: string;
  msgVariant?: 'ok' | 'err';
  msgVisible?: boolean;
}

const QUALITY_OPTIONS = [
  { value: '27', label: 'FLAC 24-bit / ≤192kHz — Max (default)' },
  { value: '7',  label: 'FLAC 24-bit / ≤96kHz — Hi-Res'        },
  { value: '6',  label: 'FLAC 16-bit / 44.1kHz — CD'            },
  { value: '5',  label: 'MP3 320kbps'                            },
];

export function SettingsScreen({ settings = {}, tokenSaved = false, onSave, msgText, msgVariant, msgVisible }: SettingsScreenProps) {
  const [token, setToken]               = useState('');
  const [downloadsDir, setDownloadsDir] = useState(settings.downloads_dir ?? '');
  const [musicDir, setMusicDir]         = useState(settings.music_dir ?? '');
  const [quality, setQuality]           = useState(String(settings.music_quality ?? 27));
  const [lyrics, setLyrics]             = useState(settings.download_lyrics ?? false);
  const [explicit, setExplicit]         = useState(settings.prefer_explicit ?? false);
  const [webhook, setWebhook]           = useState(settings.notify_webhook_url ?? '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave?.({ qobuz_token: token, downloads_dir: downloadsDir, music_dir: musicDir, music_quality: parseInt(quality), download_lyrics: lyrics, prefer_explicit: explicit, notify_webhook_url: webhook });
  };

  return (
    <>
      <SectionHead title="Settings" num="04" tag="configuration" />

      <InfoCard
        title="How to get your Qobuz auth token"
        steps={[
          <>Log in at <code>play.qobuz.com</code></>,
          <><kbd>F12</kbd> → <b>Application</b> → <b>Local Storage</b> → <code>https://play.qobuz.com</code></>,
          <>Find the <code>localuser</code> key, copy the <code>token</code> string from its JSON value</>,
        ]}
      />

      <Card>
        <form onSubmit={handleSubmit}>
          <Field
            label="qobuz auth token"
            required
            labelRight={
              <span style={{ color: tokenSaved ? 'var(--success)' : 'var(--faint)' }}>
                {tokenSaved ? 'saved' : 'not set'}
              </span>
            }
            hint="Never sent anywhere but your own server. Stored in the local SQLite DB."
          >
            <input type="password" placeholder="paste your token to update" value={token} onChange={e => setToken(e.target.value)} />
          </Field>

          <Field label="downloads directory" labelRight="scratch space">
            <input type="text" placeholder="/downloads" value={downloadsDir} onChange={e => setDownloadsDir(e.target.value)} />
          </Field>

          <Field
            label="music library directory"
            labelRight="final destination"
            hint={<>Tagged files land here as <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--paper)', padding: '1px 5px', border: '1px solid var(--line)', borderRadius: 2 }}>Artist / Album / Title.FLAC</code></>}
          >
            <input type="text" placeholder="/music" value={musicDir} onChange={e => setMusicDir(e.target.value)} />
          </Field>

          <Field label="download quality" labelRight="applied to all downloads" hint="Qobuz quality tier. Higher tiers require a compatible subscription.">
            <select value={quality} onChange={e => setQuality(e.target.value)}>
              {QUALITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </Field>

          <Field label="download synced lyrics" labelRight=".lrc sidecars" hint={<>Saves a <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--paper)', padding: '1px 5px', border: '1px solid var(--line)', borderRadius: 2 }}>Title.lrc</code> next to each track.</>}>
            <Checkbox id="download_lyrics" label="fetch lyrics from LRCLIB for every track" checked={lyrics} onChange={e => setLyrics(e.target.checked)} />
          </Field>

          <Field label="prefer explicit tracks" labelRight="clean → explicit" hint="When on, each clean track in a playlist is replaced by its explicit version before downloading.">
            <Checkbox id="prefer_explicit" label="swap clean tracks for explicit twins on playlist downloads" checked={explicit} onChange={e => setExplicit(e.target.checked)} />
          </Field>

          <Field label="notification webhook" labelRight="optional" hint="Discord, Slack, or ntfy compatible. Posted when any job finishes or errors.">
            <input type="url" placeholder="https://discord.com/api/webhooks/…" value={webhook} onChange={e => setWebhook(e.target.value)} />
          </Field>

          <ButtonRow>
            <Button type="submit" variant="primary">Save changes</Button>
            <Msg text={msgText} variant={msgVariant} visible={msgVisible} />
          </ButtonRow>
        </form>
      </Card>
    </>
  );
}
