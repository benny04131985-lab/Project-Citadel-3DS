#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()

sound_source = root / "src" / "MacSrc" / "SDLSound.c"
alog_source = root / "src" / "GameSrc" / "audiolog.c"

sound_output = root / "src" / "MacSrc" / "SDLSound_3DS_V12E.c"
alog_output = root / "src" / "GameSrc" / "audiolog_3DS_V12E.c"

for path in (sound_source, alog_source):
    if not path.is_file():
        print(f"ERROR: missing {path.relative_to(root)}", file=sys.stderr)
        raise SystemExit(1)

sound = sound_source.read_text(encoding="utf-8")
alog = alog_source.read_text(encoding="utf-8")

if "PROJECT CITADEL SDLSOUND V12E" in sound:
    print("ERROR: SDLSound.c already contains V12E.", file=sys.stderr)
    raise SystemExit(1)

if "PROJECT CITADEL SDLSOUND V12D" not in sound:
    print(
        "ERROR: V12E expects the currently working V12D SDLSound.c.",
        file=sys.stderr,
    )
    raise SystemExit(1)

if "PROJECT CITADEL AUDIOLOG V12E" in alog:
    print("ERROR: audiolog.c already contains V12E.", file=sys.stderr)
    raise SystemExit(1)

# ------------------------------------------------------------------
# SDLSound.c
# ------------------------------------------------------------------
sound = sound.replace(
    '#warning "PROJECT CITADEL SDLSOUND V12D: protected speech and audio-log channel is ACTIVE"',
    '#warning "PROJECT CITADEL SDLSOUND V12E: native Afile speech stream is ACTIVE"',
    1,
)

device_anchor = "extern SDL_AudioDeviceID device;\n"
if device_anchor not in sound:
    print("ERROR: SDLSound device declaration not found.", file=sys.stderr)
    raise SystemExit(1)

sound = sound.replace(
    device_anchor,
    device_anchor + "extern SDL_AudioStream *cutscene_audiostream;\n",
    1,
)

counter_anchor = "static Uint32 citadel_v12d_alog_replaced = 0;\n"
if counter_anchor not in sound:
    print("ERROR: V12D counter block not found.", file=sys.stderr)
    raise SystemExit(1)

sound = sound.replace(
    counter_anchor,
    counter_anchor
    + "\n"
      "static volatile Uint32 citadel_v12e_stream_callbacks = 0;\n"
      "static volatile Uint32 citadel_v12e_stream_bytes = 0;\n",
    1,
)

callback_start = sound.find("static void citadel_v12c_audio_callback(")
callback_end = sound.find(
    "\nstatic void citadel_v12c_decoded_clear(",
    callback_start,
)

if callback_start < 0 or callback_end < 0:
    print("ERROR: V12C callback not found.", file=sys.stderr)
    raise SystemExit(1)

callback = sound[callback_start:callback_end]
closing = callback.rfind("\n}")

if closing < 0:
    print("ERROR: callback closing brace not found.", file=sys.stderr)
    raise SystemExit(1)

voice_mix = r'''
    /*
     * Audio logs, SHODAN speech, barks and cutscenes arrive through
     * cutscene_audiostream. Pull its converted PCM16 stereo output and
     * add it to the already mixed DIGIFX frame.
     */
    if (cutscene_audiostream != NULL) {
        Uint8 voice_chunk[1024];
        int mixed_bytes = 0;

        while (mixed_bytes < len) {
            int requested = len - mixed_bytes;
            int received;

            if (requested > (int)sizeof(voice_chunk))
                requested = (int)sizeof(voice_chunk);

            received = SDL_AudioStreamGet(
                cutscene_audiostream,
                voice_chunk,
                requested);

            if (received <= 0)
                break;

            SDL_MixAudioFormat(
                stream + mixed_bytes,
                voice_chunk,
                AUDIO_S16SYS,
                (Uint32)received,
                SDL_MIX_MAXVOLUME);

            mixed_bytes += received;
            citadel_v12e_stream_bytes += (Uint32)received;
        }

        if (mixed_bytes > 0)
            ++citadel_v12e_stream_callbacks;
    }
'''

callback = callback[:closing] + "\n" + voice_mix.strip("\n") + callback[closing:]
sound = sound[:callback_start] + callback + sound[callback_end:]

rate_anchor = "\nstatic int citadel_v12c_open_audio(void)\n"
if rate_anchor not in sound:
    print("ERROR: audio-open anchor not found.", file=sys.stderr)
    raise SystemExit(1)

rate_function = r'''
int citadel_3ds_audio_output_rate(void)
{
    if (citadel_v12c_audio_spec.freq > 0)
        return citadel_v12c_audio_spec.freq;

    return CITADEL_V12C_REQUEST_RATE;
}
'''

sound = sound.replace(
    rate_anchor,
    "\n" + rate_function.strip("\n") + "\n" + rate_anchor.lstrip("\n"),
    1,
)

shutdown_start = sound.find("static void citadel_v12c_audio_shutdown(void)")
shutdown_end = sound.find(
    "\nstatic int citadel_v12c_open_audio(void)",
    shutdown_start,
)

if shutdown_start < 0 or shutdown_end < 0:
    print("ERROR: shutdown function not found.", file=sys.stderr)
    raise SystemExit(1)

shutdown = sound[shutdown_start:shutdown_end]
close_anchor = "    SDL_CloseAudioDevice(device);\n"

if close_anchor not in shutdown:
    print("ERROR: SDL_CloseAudioDevice anchor not found.", file=sys.stderr)
    raise SystemExit(1)

shutdown = shutdown.replace(
    close_anchor,
    '    citadel_v12c_log(\n'
    '        "VOICE_STREAM SUMMARY callbacks=%u bytes=%u output_rate=%d",\n'
    '        (unsigned int)citadel_v12e_stream_callbacks,\n'
    '        (unsigned int)citadel_v12e_stream_bytes,\n'
    '        citadel_v12c_audio_spec.freq);\n\n'
    + close_anchor,
    1,
)

sound = sound[:shutdown_start] + shutdown + sound[shutdown_end:]

sound = sound.replace("AUDIO_3DS_V12D.log", "AUDIO_3DS_V12E.log")
sound = sound.replace(
    "PROJECT CITADEL AUDIO V12D START",
    "PROJECT CITADEL AUDIO V12E START",
)

# ------------------------------------------------------------------
# audiolog.c
# ------------------------------------------------------------------
alog_device_anchor = "extern SDL_AudioDeviceID device;\n"
if alog_device_anchor not in alog:
    print("ERROR: audiolog device declaration not found.", file=sys.stderr)
    raise SystemExit(1)

alog_helpers = r'''
#if defined(__3DS__) || defined(_3DS)

#warning "PROJECT CITADEL AUDIOLOG V12E: Afile speech streaming is ACTIVE"

extern int citadel_3ds_audio_output_rate(void);

static int citadel_v12e_voice_email = -1;
static int citadel_v12e_voice_source_rate = 0;
static int citadel_v12e_voice_output_rate = 0;
static int citadel_v12e_voice_initial_blocks = 0;
static int citadel_v12e_voice_blocks_fed = 0;
static bool citadel_v12e_voice_flushed = false;

static void citadel_v12e_voice_log(
    const char *tag,
    int email,
    int value1,
    int value2)
{
    FILE *file = fopen("VOICE_3DS_V12E.log", "a");

    if (file == NULL)
        return;

    fprintf(
        file,
        "%s email=%d value1=%d value2=%d\n",
        tag,
        email,
        value1,
        value2);

    fflush(file);
    fclose(file);
}

#endif
'''

alog = alog.replace(
    alog_device_anchor,
    alog_device_anchor + alog_helpers,
    1,
)

play_pos = alog.find("errtype audiolog_play(int email_id)")
palog_pos = alog.find("    Afile *palog;\n", play_pos)

if play_pos < 0 or palog_pos < 0:
    print("ERROR: audiolog_play declarations not found.", file=sys.stderr)
    raise SystemExit(1)

palog_end = palog_pos + len("    Afile *palog;\n")
alog = (
    alog[:palog_end]
    + "\n"
      "#if defined(__3DS__) || defined(_3DS)\n"
      "    citadel_v12e_voice_log(\n"
      "        \"VOICE REQUEST\",\n"
      "        email_id,\n"
      "        AUDIOLOG_BASE_ID + email_id,\n"
      "        0);\n"
      "#endif\n"
    + alog[palog_end:]
)

length_anchor = "    audiolog_audiobuffer_size = AfileAudioLength(palog);\n"
if length_anchor not in alog:
    print("ERROR: AfileAudioLength anchor not found.", file=sys.stderr)
    raise SystemExit(1)

alog = alog.replace(
    length_anchor,
    "#if defined(__3DS__) || defined(_3DS)\n"
    "    citadel_v12e_voice_email = email_id;\n"
    "    citadel_v12e_voice_source_rate = fix_int(palog->a.sampleRate);\n"
    "    citadel_v12e_voice_output_rate = citadel_3ds_audio_output_rate();\n"
    "    citadel_v12e_voice_blocks_fed = 0;\n"
    "    citadel_v12e_voice_flushed = false;\n"
    "#endif\n\n"
    + length_anchor
    + "#if defined(__3DS__) || defined(_3DS)\n"
      "    citadel_v12e_voice_initial_blocks = audiolog_audiobuffer_size;\n"
      "#endif\n",
    1,
)

stream_anchor = (
    "    cutscene_audiostream = "
    "SDL_NewAudioStream(AUDIO_U8, 1, fix_int(palog->a.sampleRate), "
    "AUDIO_S16SYS, 2, 48000);\n"
)

if stream_anchor not in alog:
    print("ERROR: SDL_NewAudioStream voice anchor not found.", file=sys.stderr)
    raise SystemExit(1)

stream_replacement = r'''#if defined(__3DS__) || defined(_3DS)
    cutscene_audiostream = SDL_NewAudioStream(
        AUDIO_U8,
        1,
        citadel_v12e_voice_source_rate,
        AUDIO_S16SYS,
        2,
        citadel_v12e_voice_output_rate);

    citadel_v12e_voice_log(
        "VOICE OPEN",
        email_id,
        citadel_v12e_voice_source_rate,
        citadel_v12e_voice_output_rate);
#else
    cutscene_audiostream = SDL_NewAudioStream(
        AUDIO_U8,
        1,
        fix_int(palog->a.sampleRate),
        AUDIO_S16SYS,
        2,
        48000);
#endif
'''

alog = alog.replace(stream_anchor, stream_replacement, 1)

put_anchor = (
    "            SDL_AudioStreamPut(cutscene_audiostream, "
    "audiolog_audiobuffer_pos, MOVIE_DEFAULT_BLOCKLEN);\n"
    "            audiolog_audiobuffer_pos += MOVIE_DEFAULT_BLOCKLEN;\n"
    "            audiolog_audiobuffer_size--;\n"
)

if put_anchor not in alog:
    print("ERROR: audiolog stream-feed block not found.", file=sys.stderr)
    raise SystemExit(1)

alog = alog.replace(
    put_anchor,
    put_anchor
    + "#if defined(__3DS__) || defined(_3DS)\n"
      "            ++citadel_v12e_voice_blocks_fed;\n"
      "\n"
      "            if (audiolog_audiobuffer_size == 0\n"
      "                && !citadel_v12e_voice_flushed) {\n"
      "                SDL_AudioStreamFlush(cutscene_audiostream);\n"
      "                citadel_v12e_voice_flushed = true;\n"
      "\n"
      "                citadel_v12e_voice_log(\n"
      "                    \"VOICE FLUSH\",\n"
      "                    citadel_v12e_voice_email,\n"
      "                    citadel_v12e_voice_blocks_fed,\n"
      "                    SDL_AudioStreamAvailable(cutscene_audiostream));\n"
      "            }\n"
      "#endif\n",
    1,
)

drain_anchor = (
    "        if (SDL_AudioStreamAvailable(cutscene_audiostream) == 0)\n"
    "            audiolog_stop();\n"
)

if drain_anchor not in alog:
    print("ERROR: audiolog drain condition not found.", file=sys.stderr)
    raise SystemExit(1)

alog = alog.replace(
    drain_anchor,
    "        if (audiolog_audiobuffer_size == 0\n"
    "            && SDL_AudioStreamAvailable(cutscene_audiostream) == 0)\n"
    "            audiolog_stop();\n",
    1,
)

stop_anchor = "    curr_alog = -1;\n"
if stop_anchor not in alog:
    print("ERROR: audiolog stop reset not found.", file=sys.stderr)
    raise SystemExit(1)

alog = alog.replace(
    stop_anchor,
    "#if defined(__3DS__) || defined(_3DS)\n"
    "    if (citadel_v12e_voice_email >= 0) {\n"
    "        citadel_v12e_voice_log(\n"
    "            \"VOICE STOP\",\n"
    "            citadel_v12e_voice_email,\n"
    "            citadel_v12e_voice_blocks_fed,\n"
    "            citadel_v12e_voice_initial_blocks);\n"
    "    }\n"
    "\n"
    "    citadel_v12e_voice_email = -1;\n"
    "    citadel_v12e_voice_source_rate = 0;\n"
    "    citadel_v12e_voice_output_rate = 0;\n"
    "    citadel_v12e_voice_initial_blocks = 0;\n"
    "    citadel_v12e_voice_blocks_fed = 0;\n"
    "    citadel_v12e_voice_flushed = false;\n"
    "#endif\n\n"
    + stop_anchor,
    1,
)

sound_output.write_text(sound, encoding="utf-8", newline="\n")
alog_output.write_text(alog, encoding="utf-8", newline="\n")

print(f"Created: {sound_output.relative_to(root)}")
print(f"Created: {alog_output.relative_to(root)}")
print("Original files were left unchanged.")
print("Install with:")
print(
    "  mv src/MacSrc/SDLSound_3DS_V12E.c "
    "src/MacSrc/SDLSound.c"
)
print(
    "  mv src/GameSrc/audiolog_3DS_V12E.c "
    "src/GameSrc/audiolog.c"
)
