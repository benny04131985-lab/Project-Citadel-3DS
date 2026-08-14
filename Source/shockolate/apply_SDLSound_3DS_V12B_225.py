#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()
source = root / "src" / "MacSrc" / "SDLSound.c"
output = root / "src" / "MacSrc" / "SDLSound_3DS_V12B.c"

if not source.is_file():
    print(
        "ERROR: src/MacSrc/SDLSound.c was not found. "
        "Run this script from the Shockolate project root.",
        file=sys.stderr,
    )
    raise SystemExit(1)

text = source.read_text(encoding="utf-8")

if "PROJECT CITADEL SDLSOUND V12B" in text:
    print("ERROR: SDLSound.c already contains V12B.", file=sys.stderr)
    raise SystemExit(1)

comment = "// Sound stubs that do nothing, when SDL Mixer is not found"
comment_pos = text.find(comment)
if comment_pos < 0:
    print(
        "ERROR: Could not locate the ENABLE_SOUND=OFF stub branch.",
        file=sys.stderr,
    )
    raise SystemExit(1)

branch_start = text.rfind("#else", 0, comment_pos)
branch_end = text.find("#endif", comment_pos)

if branch_start < 0 or branch_end < 0:
    print(
        "ERROR: Could not locate the stub branch boundaries.",
        file=sys.stderr,
    )
    raise SystemExit(1)

branch_end += len("#endif")

replacement = r'''#else

#if defined(__3DS__) || defined(_3DS)

#warning "PROJECT CITADEL SDLSOUND V12B: original Resource 225 VOC playback is ACTIVE"

#include <SDL.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CITADEL_V12B_TEST_RESOURCE 225
#define CITADEL_V12B_REQUEST_RATE 32000
#define CITADEL_V12B_REQUEST_SAMPLES 1024

extern SDL_AudioDeviceID device;

static SDL_AudioSpec citadel_v12b_audio_spec;
static bool citadel_v12b_audio_ready = false;
static bool citadel_v12b_audio_attempted = false;
static int citadel_v12b_current_ref = 0;

static void citadel_v12b_log(const char *fmt, ...)
{
    FILE *file;
    va_list args;

    file = fopen("AUDIO_3DS_V12B.log", "a");
    if (file == NULL)
        return;

    va_start(args, fmt);
    vfprintf(file, fmt, args);
    va_end(args);

    fputc('\n', file);
    fflush(file);
    fclose(file);
}

static int citadel_v12b_clamp(int value, int low, int high)
{
    if (value < low)
        return low;
    if (value > high)
        return high;
    return value;
}

static Sint16 citadel_v12b_clamp_s16(int value)
{
    if (value < -32768)
        return (Sint16)-32768;
    if (value > 32767)
        return (Sint16)32767;
    return (Sint16)value;
}

static Uint32 citadel_v12b_u24le(const Uint8 *bytes)
{
    return (Uint32)bytes[0]
        | ((Uint32)bytes[1] << 8)
        | ((Uint32)bytes[2] << 16);
}

static void citadel_v12b_audio_shutdown(void)
{
    if (!citadel_v12b_audio_ready || device == 0)
        return;

    citadel_v12b_log(
        "SHUTDOWN device=%u queued=%u status=%d",
        (unsigned int)device,
        (unsigned int)SDL_GetQueuedAudioSize(device),
        (int)SDL_GetAudioDeviceStatus(device));

    SDL_ClearQueuedAudio(device);
    SDL_CloseAudioDevice(device);

    device = 0;
    citadel_v12b_audio_ready = false;
    citadel_v12b_current_ref = 0;
}

static int citadel_v12b_open_audio(void)
{
    SDL_AudioSpec wanted;
    int device_count;

    if (citadel_v12b_audio_ready)
        return OK;

    if (citadel_v12b_audio_attempted)
        return ERR_NOEFFECT;

    citadel_v12b_audio_attempted = true;
    remove("AUDIO_3DS_V12B.log");

    citadel_v12b_log(
        "PROJECT CITADEL AUDIO V12B START build=%s %s",
        __DATE__,
        __TIME__);

    device_count = SDL_GetNumAudioDevices(0);
    citadel_v12b_log(
        "PLAYBACK device_count=%d first_name=%s",
        device_count,
        device_count > 0 && SDL_GetAudioDeviceName(0, 0) != NULL
            ? SDL_GetAudioDeviceName(0, 0)
            : "(default)");

    SDL_zero(wanted);
    SDL_zero(citadel_v12b_audio_spec);

    wanted.freq = CITADEL_V12B_REQUEST_RATE;
    wanted.format = AUDIO_S16SYS;
    wanted.channels = 2;
    wanted.samples = CITADEL_V12B_REQUEST_SAMPLES;
    wanted.callback = NULL;
    wanted.userdata = NULL;

    SDL_ClearError();
    device = SDL_OpenAudioDevice(
        NULL,
        0,
        &wanted,
        &citadel_v12b_audio_spec,
        SDL_AUDIO_ALLOW_FREQUENCY_CHANGE
            | SDL_AUDIO_ALLOW_SAMPLES_CHANGE);

    citadel_v12b_log(
        "OPEN device=%u error=\"%s\"",
        (unsigned int)device,
        SDL_GetError());

    if (device == 0) {
        citadel_v12b_log("RESULT FAIL: SDL_OpenAudioDevice");
        return ERR_NOEFFECT;
    }

    citadel_v12b_log(
        "OBTAINED freq=%d format=0x%04X channels=%u "
        "samples=%u size=%u",
        citadel_v12b_audio_spec.freq,
        (unsigned int)citadel_v12b_audio_spec.format,
        (unsigned int)citadel_v12b_audio_spec.channels,
        (unsigned int)citadel_v12b_audio_spec.samples,
        (unsigned int)citadel_v12b_audio_spec.size);

    if (citadel_v12b_audio_spec.format != AUDIO_S16SYS
        || citadel_v12b_audio_spec.channels != 2) {
        citadel_v12b_log("RESULT FAIL: expected PCM16 stereo");
        SDL_CloseAudioDevice(device);
        device = 0;
        return ERR_NOEFFECT;
    }

    citadel_v12b_audio_ready = true;
    atexit(citadel_v12b_audio_shutdown);
    SDL_PauseAudioDevice(device, 0);

    citadel_v12b_log(
        "RESULT READY status=%d",
        (int)SDL_GetAudioDeviceStatus(device));

    return OK;
}

static int citadel_v12b_decode_and_queue_voc(
    int snd_ref,
    int len,
    const Uint8 *voc,
    const snd_digi_parms *dprm)
{
    Uint16 data_offset;
    Uint16 version;
    Uint16 checksum;
    int position;
    Uint8 block_type;
    Uint32 block_length;
    Uint8 time_constant;
    Uint8 codec;
    int rate_denominator;
    int source_rate;
    const Uint8 *source_pcm;
    Uint32 source_frames;
    Uint32 output_frames;
    Uint32 output_bytes;
    Sint16 *output_pcm;
    Uint32 output_frame;
    int volume;
    int pan;
    int left_pan;
    int right_pan;
    int left_gain;
    int right_gain;
    int queue_result;

    if (voc == NULL || dprm == NULL || len < 27) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=short-or-null len=%d",
            snd_ref,
            len);
        return ERR_NOEFFECT;
    }

    if (memcmp(voc, "Creative Voice File", 19) != 0
        || voc[19] != 0x1A) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=bad-header "
            "first=%02X%02X%02X%02X",
            snd_ref,
            voc[0],
            voc[1],
            voc[2],
            voc[3]);
        return ERR_NOEFFECT;
    }

    data_offset = (Uint16)(
        (Uint16)voc[20]
        | ((Uint16)voc[21] << 8));
    version = (Uint16)(
        (Uint16)voc[22]
        | ((Uint16)voc[23] << 8));
    checksum = (Uint16)(
        (Uint16)voc[24]
        | ((Uint16)voc[25] << 8));

    if ((int)data_offset >= len) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=bad-offset offset=%u len=%d",
            snd_ref,
            (unsigned int)data_offset,
            len);
        return ERR_NOEFFECT;
    }

    position = (int)data_offset;
    block_type = voc[position++];

    if (block_type != 1 || position + 3 > len) {
        citadel_v12b_log(
            "VOC UNSUPPORTED ref=%d version=0x%04X "
            "first_block=%u",
            snd_ref,
            (unsigned int)version,
            (unsigned int)block_type);
        return ERR_NOEFFECT;
    }

    block_length = citadel_v12b_u24le(voc + position);
    position += 3;

    if (block_length < 2
        || position + (int)block_length > len) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=bad-block-length "
            "block_len=%u remaining=%d",
            snd_ref,
            (unsigned int)block_length,
            len - position);
        return ERR_NOEFFECT;
    }

    time_constant = voc[position++];
    codec = voc[position++];

    if (codec != 0) {
        citadel_v12b_log(
            "VOC UNSUPPORTED ref=%d block=1 codec=%u",
            snd_ref,
            (unsigned int)codec);
        return ERR_NOEFFECT;
    }

    rate_denominator = 256 - (int)time_constant;
    if (rate_denominator <= 0) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=bad-time-constant tc=%u",
            snd_ref,
            (unsigned int)time_constant);
        return ERR_NOEFFECT;
    }

    source_rate =
        (1000000 + rate_denominator / 2)
        / rate_denominator;

    source_pcm = voc + position;
    source_frames = block_length - 2;

    if (source_frames == 0) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=no-pcm",
            snd_ref);
        return ERR_NOEFFECT;
    }

    output_frames = (Uint32)(
        ((uint64_t)source_frames
            * (uint64_t)citadel_v12b_audio_spec.freq
            + (uint64_t)source_rate - 1)
        / (uint64_t)source_rate);

    output_bytes =
        output_frames * 2U * (Uint32)sizeof(Sint16);

    output_pcm = (Sint16 *)SDL_malloc(output_bytes);
    if (output_pcm == NULL) {
        citadel_v12b_log(
            "VOC FAIL ref=%d reason=alloc bytes=%u",
            snd_ref,
            (unsigned int)output_bytes);
        return ERR_NOEFFECT;
    }

    volume = citadel_v12b_clamp((int)dprm->vol, 0, 127);
    pan = citadel_v12b_clamp((int)dprm->pan, 1, 127);

    if (pan <= 64) {
        left_pan = 127;
        right_pan = (pan * 127) / 64;
    } else {
        right_pan = 127;
        left_pan = ((127 - pan) * 127) / 63;
    }

    left_gain = (volume * left_pan) / 127;
    right_gain = (volume * right_pan) / 127;

    for (output_frame = 0;
         output_frame < output_frames;
         ++output_frame) {
        uint64_t source_numerator =
            (uint64_t)output_frame
            * (uint64_t)source_rate;
        Uint32 source_index = (Uint32)(
            source_numerator
            / (uint64_t)citadel_v12b_audio_spec.freq);
        Uint32 source_fraction = (Uint32)(
            source_numerator
            % (uint64_t)citadel_v12b_audio_spec.freq);
        Uint32 next_index;
        int sample_a;
        int sample_b;
        int interpolated;
        int left_sample;
        int right_sample;

        if (source_index >= source_frames)
            source_index = source_frames - 1;

        next_index = source_index + 1;
        if (next_index >= source_frames)
            next_index = source_index;

        sample_a = ((int)source_pcm[source_index] - 128) << 8;
        sample_b = ((int)source_pcm[next_index] - 128) << 8;

        interpolated =
            sample_a
            + (int)(
                ((int64_t)(sample_b - sample_a)
                    * (int64_t)source_fraction)
                / (int64_t)citadel_v12b_audio_spec.freq);

        left_sample = (interpolated * left_gain) / 127;
        right_sample = (interpolated * right_gain) / 127;

        output_pcm[output_frame * 2] =
            citadel_v12b_clamp_s16(left_sample);
        output_pcm[output_frame * 2 + 1] =
            citadel_v12b_clamp_s16(right_sample);
    }

    SDL_ClearError();
    queue_result = SDL_QueueAudio(
        device,
        output_pcm,
        output_bytes);

    citadel_v12b_log(
        "PLAY ref=%d voc_version=0x%04X checksum=0x%04X "
        "block=%u codec=%u tc=%u source_rate=%d "
        "source_frames=%u output_frames=%u duration_ms=%u "
        "vol=%d pan=%d gains=%d,%d loops=%d pri=%d "
        "queue_result=%d queued=%u error=\"%s\"",
        snd_ref,
        (unsigned int)version,
        (unsigned int)checksum,
        (unsigned int)block_type,
        (unsigned int)codec,
        (unsigned int)time_constant,
        source_rate,
        (unsigned int)source_frames,
        (unsigned int)output_frames,
        (unsigned int)(
            (output_frames * 1000U)
            / (Uint32)citadel_v12b_audio_spec.freq),
        volume,
        pan,
        left_gain,
        right_gain,
        (int)dprm->loops,
        (int)dprm->pri,
        queue_result,
        (unsigned int)SDL_GetQueuedAudioSize(device),
        SDL_GetError());

    SDL_free(output_pcm);

    if (queue_result < 0)
        return ERR_NOEFFECT;

    citadel_v12b_current_ref = snd_ref;
    return 0;
}

int snd_start_digital(void)
{
    return citadel_v12b_open_audio();
}

int snd_sample_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    Uint32 queued;

    if (!citadel_v12b_audio_ready
        && citadel_v12b_open_audio() != OK)
        return ERR_NOEFFECT;

    citadel_v12b_log(
        "REQUEST ref=%d len=%d loops=%d pri=%d vol=%d pan=%d",
        snd_ref,
        len,
        dprm != NULL ? (int)dprm->loops : -999,
        dprm != NULL ? (int)dprm->pri : -999,
        dprm != NULL ? (int)dprm->vol : -999,
        dprm != NULL ? (int)dprm->pan : -999);

    if (snd_ref != CITADEL_V12B_TEST_RESOURCE) {
        citadel_v12b_log(
            "SKIP ref=%d reason=V12B-only-plays-225",
            snd_ref);
        return ERR_NOEFFECT;
    }

    queued = SDL_GetQueuedAudioSize(device);
    if (queued > 0) {
        citadel_v12b_log(
            "SKIP ref=%d reason=device-busy queued=%u",
            snd_ref,
            (unsigned int)queued);
        return ERR_NOEFFECT;
    }

    digi_parms_by_channel[0] = *dprm;

    return citadel_v12b_decode_and_queue_voc(
        snd_ref,
        len,
        (const Uint8 *)smp,
        dprm);
}

int snd_alog_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    return snd_sample_play(snd_ref, len, smp, dprm);
}

void snd_end_sample(int hnd_id)
{
    if (hnd_id != 0
        || !citadel_v12b_audio_ready
        || device == 0)
        return;

    SDL_ClearQueuedAudio(device);
    citadel_v12b_log(
        "END handle=%d ref=%d",
        hnd_id,
        citadel_v12b_current_ref);
    citadel_v12b_current_ref = 0;
}

void snd_kill_all_samples(void)
{
    if (citadel_v12b_audio_ready && device != 0)
        SDL_ClearQueuedAudio(device);

    citadel_v12b_log(
        "KILL_ALL current_ref=%d",
        citadel_v12b_current_ref);

    citadel_v12b_current_ref = 0;
}

int MacTuneLoadTheme(char *theme_base, int themeID)
{
    return OK;
}

void MacTuneKillCurrentTheme(void)
{
}

snd_digi_parms *snd_sample_parms(int hnd_id)
{
    if (hnd_id < 0 || hnd_id >= SND_MAX_SAMPLES)
        hnd_id = 0;

    return &digi_parms_by_channel[hnd_id];
}

bool snd_sample_playing(int hnd_id)
{
    if (hnd_id != 0
        || !citadel_v12b_audio_ready
        || device == 0)
        return false;

    return SDL_GetQueuedAudioSize(device) > 0;
}

void snd_sample_reload_parms(snd_digi_parms *sdp)
{
    int channel;

    if (sdp < digi_parms_by_channel
        || sdp >= digi_parms_by_channel + SND_MAX_SAMPLES)
        return;

    channel = (int)(sdp - digi_parms_by_channel);

    if (channel == 0 && snd_sample_playing(0)) {
        citadel_v12b_log(
            "PARAM_UPDATE handle=0 ref=%d vol=%d pan=%d "
            "(applies to next V12B playback)",
            (int)sdp->snd_ref,
            (int)sdp->vol,
            (int)sdp->pan);
    }
}

#else

int snd_start_digital(void) { return OK; }

int snd_sample_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    return OK;
}

int snd_alog_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    return OK;
}

void snd_end_sample(int hnd_id) {}
void snd_kill_all_samples(void) {}
int MacTuneLoadTheme(char *theme_base, int themeID) { return OK; }
void MacTuneKillCurrentTheme(void) {}

snd_digi_parms *snd_sample_parms(int hnd_id)
{
    return &digi_parms_by_channel[0];
}

bool snd_sample_playing(int hnd_id) { return false; }
void snd_sample_reload_parms(snd_digi_parms *sdp) {}

#endif

#endif'''

patched = text[:branch_start] + replacement + text[branch_end:]
output.write_text(patched, encoding="utf-8", newline="\n")

print(f"Created: {output.relative_to(root)}")
print("Original SDLSound.c was left unchanged.")
print()
print("Install with:")
print(
    "  mv src/MacSrc/SDLSound_3DS_V12B.c "
    "src/MacSrc/SDLSound.c"
)
