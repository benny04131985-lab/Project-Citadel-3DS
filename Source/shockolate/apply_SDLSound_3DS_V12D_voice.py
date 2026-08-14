#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()
source = root / "src" / "MacSrc" / "SDLSound.c"
output = root / "src" / "MacSrc" / "SDLSound_3DS_V12D.c"

if not source.is_file():
    print(
        "ERROR: src/MacSrc/SDLSound.c was not found. "
        "Run this script from the Shockolate project root.",
        file=sys.stderr,
    )
    raise SystemExit(1)

text = source.read_text(encoding="utf-8")

if "PROJECT CITADEL SDLSOUND V12D" in text:
    print("ERROR: SDLSound.c already contains V12D.", file=sys.stderr)
    raise SystemExit(1)

if "PROJECT CITADEL SDLSOUND V12C" not in text:
    print(
        "ERROR: V12D expects the currently working V12C SDLSound.c. "
        "Restore or reinstall V12C first.",
        file=sys.stderr,
    )
    raise SystemExit(1)

text = text.replace(
    '#warning "PROJECT CITADEL SDLSOUND V12C: multivoice VOC mixer is ACTIVE"',
    '#warning "PROJECT CITADEL SDLSOUND V12D: protected speech and audio-log channel is ACTIVE"',
    1,
)

defines_anchor = "#define CITADEL_V12C_EVENT_LOG_LIMIT       512\n"
if defines_anchor not in text:
    print("ERROR: Could not locate V12C define block.", file=sys.stderr)
    raise SystemExit(1)

text = text.replace(
    defines_anchor,
    defines_anchor
    + "#define CITADEL_V12D_SPEECH_CHANNEL "
      "(SND_MAX_SAMPLES - 1)\n",
    1,
)

counter_anchor = "static Uint32 citadel_v12c_event_logs = 0;\n"
if counter_anchor not in text:
    print("ERROR: Could not locate V12C counter block.", file=sys.stderr)
    raise SystemExit(1)

text = text.replace(
    counter_anchor,
    counter_anchor
    + "\n"
      "static Uint32 citadel_v12d_alog_requests = 0;\n"
      "static Uint32 citadel_v12d_alog_started = 0;\n"
      "static Uint32 citadel_v12d_alog_failures = 0;\n"
      "static Uint32 citadel_v12d_alog_replaced = 0;\n",
    1,
)

choose_start = text.find(
    "static int citadel_v12c_choose_channel_locked(int priority)"
)
choose_end = text.find("\nint snd_start_digital(void)", choose_start)

if choose_start < 0 or choose_end < 0:
    print("ERROR: Could not locate V12C channel allocator.", file=sys.stderr)
    raise SystemExit(1)

old_choose = text[choose_start:choose_end]
new_choose = old_choose.replace(
    "channel < SND_MAX_SAMPLES",
    "channel < CITADEL_V12D_SPEECH_CHANNEL",
)

if new_choose == old_choose:
    print("ERROR: Channel allocator was not modified.", file=sys.stderr)
    raise SystemExit(1)

text = text[:choose_start] + new_choose + text[choose_end:]

play_start = text.find("\nint snd_sample_play(\n")
play_end = text.find("\nvoid snd_end_sample(int hnd_id)", play_start)

if play_start < 0 or play_end < 0:
    print("ERROR: Could not locate V12C playback functions.", file=sys.stderr)
    raise SystemExit(1)

replacement = r'''
static int citadel_v12d_start_voice(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm,
    bool is_speech)
{
    citadel_v12c_decoded_sound decoded;
    citadel_v12c_voice *voice;
    int channel;
    int priority;
    int loops;
    int replaced_ref = 0;

    ++citadel_v12c_requests;

    if (is_speech) {
        ++citadel_v12d_alog_requests;

        citadel_v12c_log(
            "ALOG REQUEST ref=%d len=%d loops=%d pri=%d "
            "vol=%d pan=%d first=%02X%02X%02X%02X",
            snd_ref,
            len,
            dprm != NULL ? (int)dprm->loops : -999,
            dprm != NULL ? (int)dprm->pri : -999,
            dprm != NULL ? (int)dprm->vol : -999,
            dprm != NULL ? (int)dprm->pan : -999,
            smp != NULL && len > 0 ? (unsigned int)smp[0] : 0U,
            smp != NULL && len > 1 ? (unsigned int)smp[1] : 0U,
            smp != NULL && len > 2 ? (unsigned int)smp[2] : 0U,
            smp != NULL && len > 3 ? (unsigned int)smp[3] : 0U);
    }

    if (dprm == NULL || smp == NULL || len <= 0) {
        if (is_speech) {
            ++citadel_v12d_alog_failures;
            citadel_v12c_log(
                "ALOG FAIL ref=%d reason=bad-arguments",
                snd_ref);
        }
        return ERR_NOEFFECT;
    }

    if (!citadel_v12c_audio_ready
        && citadel_v12c_open_audio() != OK) {
        if (is_speech) {
            ++citadel_v12d_alog_failures;
            citadel_v12c_log(
                "ALOG FAIL ref=%d reason=audio-device",
                snd_ref);
        }
        return ERR_NOEFFECT;
    }

    if (citadel_v12c_decode_voc(
            snd_ref,
            len,
            (const Uint8 *)smp,
            &decoded) != OK) {
        if (is_speech) {
            ++citadel_v12d_alog_failures;
            citadel_v12c_log(
                "ALOG FAIL ref=%d reason=VOC-decode",
                snd_ref);
        }
        return ERR_NOEFFECT;
    }

    priority = is_speech ? 127 : (int)dprm->pri;
    loops = dprm->loops > 0 ? (int)dprm->loops : -1;

    SDL_LockAudioDevice(device);

    if (is_speech) {
        channel = CITADEL_V12D_SPEECH_CHANNEL;

        if (citadel_v12c_voices[channel].active
            || citadel_v12c_voices[channel].pcm != NULL) {
            replaced_ref = citadel_v12c_voices[channel].snd_ref;
            ++citadel_v12d_alog_replaced;
            citadel_v12c_free_voice_locked(channel);
        }
    } else {
        channel = citadel_v12c_choose_channel_locked(priority);
    }

    if (channel < 0) {
        SDL_UnlockAudioDevice(device);
        citadel_v12c_decoded_clear(&decoded);

        if (is_speech) {
            ++citadel_v12d_alog_failures;
            citadel_v12c_log(
                "ALOG FAIL ref=%d reason=no-channel",
                snd_ref);
        } else if (citadel_v12c_event_logs
            < CITADEL_V12C_EVENT_LOG_LIMIT) {
            ++citadel_v12c_event_logs;
            citadel_v12c_log(
                "DROP ref=%d pri=%d reason=no-channel",
                snd_ref,
                priority);
        }

        return ERR_NOEFFECT;
    }

    voice = &citadel_v12c_voices[channel];
    SDL_memset(voice, 0, sizeof(*voice));

    voice->pcm = decoded.pcm;
    decoded.pcm = NULL;
    voice->frames = decoded.frames;
    voice->phase = 0;
    voice->step = (Uint64)(
        (((Uint64)decoded.rate) << 32)
        / (Uint64)citadel_v12c_audio_spec.freq);
    voice->loops_remaining = loops;
    voice->volume = (int)dprm->vol;
    voice->pan = (int)dprm->pan;
    voice->priority = priority;
    voice->snd_ref = snd_ref;
    voice->serial = citadel_v12c_serial++;
    voice->finished = false;
    voice->active = true;

    if (voice->step == 0)
        voice->step = 1;

    citadel_v12c_update_gains(voice);
    digi_parms_by_channel[channel] = *dprm;

    SDL_UnlockAudioDevice(device);

    ++citadel_v12c_started;

    if (is_speech) {
        ++citadel_v12d_alog_started;

        if (replaced_ref != 0) {
            citadel_v12c_log(
                "ALOG REPLACE channel=%d old_ref=%d new_ref=%d",
                channel,
                replaced_ref,
                snd_ref);
        }

        citadel_v12c_log(
            "ALOG DECODE ref=%d voc_version=0x%04X "
            "checksum=0x%04X rate=%d frames=%u "
            "duration_ms=%u block_mask=0x%08X "
            "repeat_markers=%d",
            snd_ref,
            (unsigned int)decoded.version,
            (unsigned int)decoded.checksum,
            decoded.rate,
            (unsigned int)decoded.frames,
            (unsigned int)(
                ((Uint64)decoded.frames * 1000U)
                / (Uint64)decoded.rate),
            (unsigned int)decoded.block_mask,
            decoded.internal_repeat_markers);

        citadel_v12c_log(
            "ALOG PLAY channel=%d ref=%d len=%d loops=%d "
            "pri=%d vol=%d pan=%d gains=%d,%d",
            channel,
            snd_ref,
            len,
            loops,
            priority,
            voice->volume,
            voice->pan,
            voice->left_gain,
            voice->right_gain);
    } else {
        if (snd_ref >= 0
            && snd_ref < CITADEL_V12C_LOGGED_REFS
            && !citadel_v12c_decode_logged[snd_ref]) {
            citadel_v12c_decode_logged[snd_ref] = 1;

            citadel_v12c_log(
                "DECODE ref=%d voc_version=0x%04X "
                "checksum=0x%04X rate=%d frames=%u "
                "duration_ms=%u block_mask=0x%08X "
                "repeat_markers=%d",
                snd_ref,
                (unsigned int)decoded.version,
                (unsigned int)decoded.checksum,
                decoded.rate,
                (unsigned int)decoded.frames,
                (unsigned int)(
                    ((Uint64)decoded.frames * 1000U)
                    / (Uint64)decoded.rate),
                (unsigned int)decoded.block_mask,
                decoded.internal_repeat_markers);
        }

        if (citadel_v12c_event_logs
            < CITADEL_V12C_EVENT_LOG_LIMIT) {
            ++citadel_v12c_event_logs;

            citadel_v12c_log(
                "PLAY channel=%d ref=%d len=%d loops=%d "
                "pri=%d vol=%d pan=%d gains=%d,%d",
                channel,
                snd_ref,
                len,
                loops,
                priority,
                voice->volume,
                voice->pan,
                voice->left_gain,
                voice->right_gain);
        }
    }

    return channel;
}

int snd_sample_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    return citadel_v12d_start_voice(
        snd_ref,
        len,
        smp,
        dprm,
        false);
}

int snd_alog_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    return citadel_v12d_start_voice(
        snd_ref,
        len,
        smp,
        dprm,
        true);
}
'''

text = text[:play_start] + "\n" + replacement.strip("\n") + text[play_end:]

shutdown_anchor = (
    "    SDL_CloseAudioDevice(device);\n"
    "    device = 0;\n"
)

if shutdown_anchor not in text:
    print("ERROR: Could not locate V12C shutdown close.", file=sys.stderr)
    raise SystemExit(1)

shutdown_insert = (
    '    citadel_v12c_log(\n'
    '        "ALOG SUMMARY requests=%u started=%u failures=%u replaced=%u "\n'
    '        "reserved_channel=%d",\n'
    '        (unsigned int)citadel_v12d_alog_requests,\n'
    '        (unsigned int)citadel_v12d_alog_started,\n'
    '        (unsigned int)citadel_v12d_alog_failures,\n'
    '        (unsigned int)citadel_v12d_alog_replaced,\n'
    '        CITADEL_V12D_SPEECH_CHANNEL);\n\n'
    + shutdown_anchor
)

text = text.replace(shutdown_anchor, shutdown_insert, 1)
text = text.replace("AUDIO_3DS_V12C.log", "AUDIO_3DS_V12D.log")
text = text.replace(
    "PROJECT CITADEL AUDIO V12C START",
    "PROJECT CITADEL AUDIO V12D START",
)

output.write_text(text, encoding="utf-8", newline="\n")

print(f"Created: {output.relative_to(root)}")
print("Original V12C SDLSound.c was left unchanged.")
print("Install with:")
print(
    "  mv src/MacSrc/SDLSound_3DS_V12D.c "
    "src/MacSrc/SDLSound.c"
)
