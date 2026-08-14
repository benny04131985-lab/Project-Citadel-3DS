#include "Xmi.h"
#include "MusicDevice.h"

static snd_digi_parms digi_parms_by_channel[SND_MAX_SAMPLES];

#ifdef USE_SDL_MIXER

#include <SDL_mixer.h>

static Mix_Chunk *samples_by_channel[SND_MAX_SAMPLES];

extern SDL_AudioStream *cutscene_audiostream;
extern struct MusicDevice *MusicDev;

extern void AudioStreamCallback(void *userdata, unsigned char *stream, int len);
extern void MusicCallback(void *userdata, Uint8 *stream, int len);

int snd_start_digital(void) {

    // Startup the sound system

    SDL_AudioSpec spec, obtained;
    spec.freq = 48000;
    spec.format = AUDIO_S16SYS;
    spec.channels = 2;
    spec.samples = 2048;
    spec.callback = AudioStreamCallback;
    spec.userdata = (void *)&cutscene_audiostream;

    extern SDL_AudioDeviceID device;
    device = SDL_OpenAudioDevice(NULL, 0, &spec, &obtained, 0);

    if (device == 0) {
        ERROR("Could not open SDL audio: %s", SDL_GetError());
    } else {
        INFO("Opened Music Stream, deviceID %d, freq %d, size %d, format %d, channels %d, samples %d", device,
             obtained.freq, obtained.size, obtained.format, obtained.channels, obtained.samples);
    }

    if (Mix_Init(MIX_INIT_MP3) < 0) {
        ERROR("%s: Init failed", __FUNCTION__);
    }

    if (Mix_OpenAudio(48000, AUDIO_S16SYS, 2, 2048) < 0) {
        ERROR("%s: Couldn't open audio device", __FUNCTION__);
    }

    Mix_AllocateChannels(SND_MAX_SAMPLES);

    Mix_HookMusic(MusicCallback, (void *)&MusicDev);
    Mix_VolumeMusic(MIX_MAX_VOLUME); // use max volume for music stream

    InitReadXMI();

    atexit(Mix_CloseAudio);
    atexit(SDL_CloseAudio);

    return OK;
}

int snd_sample_play(int snd_ref, int len, uchar *smp, struct snd_digi_parms *dprm) {

    // Play one of the VOC format sounds

    Mix_Chunk *sample = Mix_LoadWAV_RW(SDL_RWFromConstMem(smp, len), 1);
    if (sample == NULL) {
        DEBUG("%s: Failed to load sample", __FUNCTION__);
        return ERR_NOEFFECT;
    }

    int loops = dprm->loops > 0 ? dprm->loops - 1 : -1;
    int channel = Mix_PlayChannel(-1, sample, loops);
    if (channel < 0) {
        DEBUG("%s: Failed to play sample", __FUNCTION__);
        Mix_FreeChunk(sample);
        return ERR_NOEFFECT;
    }

    if (samples_by_channel[channel])
        Mix_FreeChunk(samples_by_channel[channel]);

    samples_by_channel[channel] = sample;
    digi_parms_by_channel[channel] = *dprm;
    snd_sample_reload_parms(&digi_parms_by_channel[channel]);

    return channel;
}

void snd_end_sample(int hnd_id) {
    Mix_HaltChannel(hnd_id);
    if (samples_by_channel[hnd_id]) {
        Mix_FreeChunk(samples_by_channel[hnd_id]);
        samples_by_channel[hnd_id] = NULL;
    }
}

bool snd_sample_playing(int hnd_id) { return Mix_Playing(hnd_id); }

snd_digi_parms *snd_sample_parms(int hnd_id) { return &digi_parms_by_channel[hnd_id]; }

void snd_kill_all_samples(void) {
    for (int channel = 0; channel < SND_MAX_SAMPLES; channel++) {
        snd_end_sample(channel);
    }

    // assume we want these too
    //    StopTheMusic(); // no, don't stop the music
    if (cutscene_audiostream != NULL)
        SDL_AudioStreamClear(cutscene_audiostream);
}

void snd_sample_reload_parms(snd_digi_parms *sdp) {
    // ignore if *sdp is not one of the items in digi_parms_by_channel[]
    if (sdp < digi_parms_by_channel || sdp > digi_parms_by_channel + SND_MAX_SAMPLES)
        return;
    int channel = sdp - digi_parms_by_channel;

    if (!Mix_Playing(channel))
        return;

    // sdp->vol ranges from 0..255
    Mix_Volume(channel, (sdp->vol * 128) / 100);

    // sdp->pan ranges from 1 (left) to 127 (right)
    uint8_t right = 2 * sdp->pan;
    Mix_SetPanning(channel, 254 - right, right);
}

int is_playing = 0;

int MacTuneLoadTheme(char *theme_base, int themeID) {
    char filename[40];
    FILE *f;
    int i;

#define NUM_SCORES 8
#define SUPERCHUNKS_PER_SCORE 4
#define NUM_TRANSITIONS 9
#define NUM_LAYERS 32
#define MAX_KEYS 10
#define NUM_LAYERABLE_SUPERCHUNKS 22
#define KEY_BAR_RESOLUTION 2

    extern uchar track_table[NUM_SCORES][SUPERCHUNKS_PER_SCORE];
    extern uchar transition_table[NUM_TRANSITIONS];
    extern uchar layering_table[NUM_LAYERS][MAX_KEYS];
    extern uchar key_table[NUM_LAYERABLE_SUPERCHUNKS][KEY_BAR_RESOLUTION];

    StopTheMusic();

    FreeXMI();

    if (strncmp(theme_base, "thm", 3)) {
        sprintf(filename, "res/sound/%s/%s.xmi", MusicDev->musicType, theme_base);
        ReadXMI(filename);
    } else {
        sprintf(filename, "res/sound/%s/thm%i.xmi", MusicDev->musicType, themeID);
        ReadXMI(filename);

        sprintf(filename, "res/sound/thm%i.bin", themeID);
        extern FILE *fopen_caseless(const char *path, const char *mode); // see caseless.c
        f = fopen_caseless(filename, "rb");
        if (f != 0) {
            fread(track_table, NUM_SCORES * SUPERCHUNKS_PER_SCORE, 1, f);
            fread(transition_table, NUM_TRANSITIONS, 1, f);
            fread(layering_table, NUM_LAYERS * MAX_KEYS, 1, f);
            fread(key_table, NUM_LAYERABLE_SUPERCHUNKS * KEY_BAR_RESOLUTION, 1, f);

            fclose(f);
        }
    }

    return OK;
}

void MacTuneKillCurrentTheme(void) { StopTheMusic(); }


#else

#if defined(__3DS__) || defined(_3DS)

#warning "PROJECT CITADEL SDLSOUND V12C: multivoice VOC mixer is ACTIVE"

#include <SDL.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CITADEL_V12C_REQUEST_RATE       32000
#define CITADEL_V12C_REQUEST_SAMPLES     1024
#define CITADEL_V12C_GAIN_MAX             127
#define CITADEL_V12C_LOGGED_REFS          2048
#define CITADEL_V12C_EVENT_LOG_LIMIT       512

extern SDL_AudioDeviceID device;

typedef struct citadel_v12c_decoded_sound {
    Uint8 *pcm;
    Uint32 frames;
    int rate;
    Uint16 version;
    Uint16 checksum;
    Uint32 block_mask;
    int internal_repeat_markers;
} citadel_v12c_decoded_sound;

typedef struct citadel_v12c_voice {
    bool active;
    bool finished;
    Uint8 *pcm;
    Uint32 frames;
    Uint64 phase;
    Uint64 step;
    int loops_remaining;
    int volume;
    int pan;
    int left_gain;
    int right_gain;
    int priority;
    int snd_ref;
    Uint32 serial;
} citadel_v12c_voice;

static SDL_AudioSpec citadel_v12c_audio_spec;
static citadel_v12c_voice citadel_v12c_voices[SND_MAX_SAMPLES];

static bool citadel_v12c_audio_ready = false;
static bool citadel_v12c_audio_attempted = false;
static Uint32 citadel_v12c_serial = 1;

static Uint32 citadel_v12c_requests = 0;
static Uint32 citadel_v12c_started = 0;
static Uint32 citadel_v12c_completed = 0;
static Uint32 citadel_v12c_stolen = 0;
static Uint32 citadel_v12c_decode_failures = 0;
static Uint32 citadel_v12c_event_logs = 0;

static Uint8 citadel_v12c_decode_logged[CITADEL_V12C_LOGGED_REFS];
static Uint8 citadel_v12c_unsupported_logged[CITADEL_V12C_LOGGED_REFS];

static void citadel_v12c_log(const char *fmt, ...)
{
    FILE *file;
    va_list args;

    file = fopen("AUDIO_3DS_V12C.log", "a");
    if (file == NULL)
        return;

    va_start(args, fmt);
    vfprintf(file, fmt, args);
    va_end(args);

    fputc('\n', file);
    fflush(file);
    fclose(file);
}

static int citadel_v12c_clamp(int value, int low, int high)
{
    if (value < low)
        return low;
    if (value > high)
        return high;
    return value;
}

static Sint16 citadel_v12c_clamp_s16(int value)
{
    if (value < -32768)
        return (Sint16)-32768;
    if (value > 32767)
        return (Sint16)32767;
    return (Sint16)value;
}

static Uint16 citadel_v12c_u16le(const Uint8 *bytes)
{
    return (Uint16)(
        (Uint16)bytes[0]
        | ((Uint16)bytes[1] << 8));
}

static Uint32 citadel_v12c_u24le(const Uint8 *bytes)
{
    return (Uint32)bytes[0]
        | ((Uint32)bytes[1] << 8)
        | ((Uint32)bytes[2] << 16);
}

static Uint32 citadel_v12c_u32le(const Uint8 *bytes)
{
    return (Uint32)bytes[0]
        | ((Uint32)bytes[1] << 8)
        | ((Uint32)bytes[2] << 16)
        | ((Uint32)bytes[3] << 24);
}

static int citadel_v12c_rate_from_tc(Uint8 time_constant)
{
    int denominator = 256 - (int)time_constant;

    if (denominator <= 0)
        return 0;

    return (1000000 + denominator / 2) / denominator;
}

static void citadel_v12c_update_gains(citadel_v12c_voice *voice)
{
    int volume;
    int pan;
    int left_pan;
    int right_pan;

    volume = citadel_v12c_clamp(
        voice->volume,
        0,
        CITADEL_V12C_GAIN_MAX);

    pan = citadel_v12c_clamp(voice->pan, 1, 127);

    if (pan <= 64) {
        left_pan = 127;
        right_pan = ((pan - 1) * 127) / 63;
    } else {
        right_pan = 127;
        left_pan = ((127 - pan) * 127) / 63;
    }

    voice->left_gain = (volume * left_pan) / 127;
    voice->right_gain = (volume * right_pan) / 127;
}

static void citadel_v12c_free_voice_locked(int channel)
{
    citadel_v12c_voice *voice;

    if (channel < 0 || channel >= SND_MAX_SAMPLES)
        return;

    voice = &citadel_v12c_voices[channel];

    if (voice->pcm != NULL)
        SDL_free(voice->pcm);

    SDL_memset(voice, 0, sizeof(*voice));
    SDL_memset(
        &digi_parms_by_channel[channel],
        0,
        sizeof(digi_parms_by_channel[channel]));
}

static void citadel_v12c_reap_finished_locked(void)
{
    int channel;

    for (channel = 0; channel < SND_MAX_SAMPLES; ++channel) {
        if (!citadel_v12c_voices[channel].active
            && citadel_v12c_voices[channel].finished) {
            citadel_v12c_free_voice_locked(channel);
        }
    }
}

static void citadel_v12c_finish_voice_from_callback(
    citadel_v12c_voice *voice)
{
    voice->active = false;
    voice->finished = true;
    ++citadel_v12c_completed;
}

static void citadel_v12c_audio_callback(
    void *userdata,
    Uint8 *stream,
    int len)
{
    Sint16 *output;
    int output_frames;
    int output_frame;
    int channel;

    (void)userdata;

    SDL_memset(stream, 0, (size_t)len);

    output = (Sint16 *)stream;
    output_frames = len / (2 * (int)sizeof(Sint16));

    for (output_frame = 0;
         output_frame < output_frames;
         ++output_frame) {
        int mixed_left = 0;
        int mixed_right = 0;

        for (channel = 0;
             channel < SND_MAX_SAMPLES;
             ++channel) {
            citadel_v12c_voice *voice =
                &citadel_v12c_voices[channel];
            Uint32 index;
            Uint32 next_index;
            Uint32 fraction;
            int sample_a;
            int sample_b;
            int sample;
            Uint64 voice_end;

            if (!voice->active
                || voice->pcm == NULL
                || voice->frames == 0) {
                continue;
            }

            voice_end = ((Uint64)voice->frames) << 32;

            while (voice->phase >= voice_end) {
                if (voice->loops_remaining < 0) {
                    voice->phase -= voice_end;
                } else if (voice->loops_remaining > 1) {
                    --voice->loops_remaining;
                    voice->phase -= voice_end;
                } else {
                    citadel_v12c_finish_voice_from_callback(voice);
                    break;
                }
            }

            if (!voice->active)
                continue;

            index = (Uint32)(voice->phase >> 32);
            fraction = (Uint32)(voice->phase & 0xFFFFFFFFULL);

            if (index >= voice->frames)
                index = voice->frames - 1;

            next_index = index + 1;
            if (next_index >= voice->frames)
                next_index = index;

            sample_a = ((int)voice->pcm[index] - 128) << 8;
            sample_b = ((int)voice->pcm[next_index] - 128) << 8;

            sample = sample_a
                + (int)(
                    ((int64_t)(sample_b - sample_a)
                        * (int64_t)fraction)
                    >> 32);

            mixed_left +=
                (sample * voice->left_gain)
                / CITADEL_V12C_GAIN_MAX;

            mixed_right +=
                (sample * voice->right_gain)
                / CITADEL_V12C_GAIN_MAX;

            voice->phase += voice->step;
        }

        output[output_frame * 2] =
            citadel_v12c_clamp_s16(mixed_left);

        output[output_frame * 2 + 1] =
            citadel_v12c_clamp_s16(mixed_right);
    }
}

static void citadel_v12c_decoded_clear(
    citadel_v12c_decoded_sound *decoded)
{
    if (decoded == NULL)
        return;

    if (decoded->pcm != NULL)
        SDL_free(decoded->pcm);

    SDL_memset(decoded, 0, sizeof(*decoded));
}

static int citadel_v12c_decode_fail(
    int snd_ref,
    const char *reason,
    int block_type,
    int codec)
{
    ++citadel_v12c_decode_failures;

    if (snd_ref >= 0
        && snd_ref < CITADEL_V12C_LOGGED_REFS
        && !citadel_v12c_unsupported_logged[snd_ref]) {
        citadel_v12c_unsupported_logged[snd_ref] = 1;

        citadel_v12c_log(
            "VOC UNSUPPORTED ref=%d reason=%s "
            "block=%d codec=%d",
            snd_ref,
            reason,
            block_type,
            codec);
    }

    return ERR_NOEFFECT;
}

static int citadel_v12c_decode_voc(
    int snd_ref,
    int len,
    const Uint8 *voc,
    citadel_v12c_decoded_sound *decoded)
{
    int pass;
    int data_offset;
    int position;
    int output_position;
    int established_rate;
    int pending_extended_rate;
    int pending_extended_codec;
    int pending_extended_channels;
    int current_codec;
    int saw_audio_data;
    Uint32 total_frames;
    Uint32 block_mask;
    int internal_repeat_markers;

    if (decoded == NULL)
        return ERR_NOEFFECT;

    SDL_memset(decoded, 0, sizeof(*decoded));

    if (voc == NULL || len < 27) {
        return citadel_v12c_decode_fail(
            snd_ref, "short-or-null", -1, -1);
    }

    if (memcmp(voc, "Creative Voice File", 19) != 0
        || voc[19] != 0x1A) {
        return citadel_v12c_decode_fail(
            snd_ref, "bad-header", -1, -1);
    }

    data_offset = (int)citadel_v12c_u16le(voc + 20);

    if (data_offset < 26 || data_offset >= len) {
        return citadel_v12c_decode_fail(
            snd_ref, "bad-data-offset", -1, -1);
    }

    decoded->version = citadel_v12c_u16le(voc + 22);
    decoded->checksum = citadel_v12c_u16le(voc + 24);

    total_frames = 0;
    established_rate = 0;
    block_mask = 0;
    internal_repeat_markers = 0;

    for (pass = 0; pass < 2; ++pass) {
        position = data_offset;
        output_position = 0;
        pending_extended_rate = 0;
        pending_extended_codec = -1;
        pending_extended_channels = 1;
        current_codec = 0;
        saw_audio_data = 0;

        while (position < len) {
            int block_type;
            Uint32 block_length;
            const Uint8 *payload;

            block_type = (int)voc[position++];

            if (block_type == 0)
                break;

            if (position + 3 > len) {
                citadel_v12c_decoded_clear(decoded);
                return citadel_v12c_decode_fail(
                    snd_ref,
                    "truncated-block-header",
                    block_type,
                    -1);
            }

            block_length = citadel_v12c_u24le(voc + position);
            position += 3;

            if (block_length > (Uint32)(len - position)) {
                citadel_v12c_decoded_clear(decoded);
                return citadel_v12c_decode_fail(
                    snd_ref,
                    "truncated-block-data",
                    block_type,
                    -1);
            }

            payload = voc + position;

            if (block_type >= 0 && block_type < 32)
                block_mask |= (1U << block_type);

            switch (block_type) {
            case 1:
            {
                int rate;
                int codec;
                int channels;
                Uint32 frames;
                const Uint8 *pcm;

                if (block_length < 2) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref, "short-type1", block_type, -1);
                }

                if (pending_extended_rate > 0) {
                    rate = pending_extended_rate;
                    codec = pending_extended_codec;
                    channels = pending_extended_channels;
                    pending_extended_rate = 0;
                    pending_extended_codec = -1;
                    pending_extended_channels = 1;
                } else {
                    rate = citadel_v12c_rate_from_tc(payload[0]);
                    codec = (int)payload[1];
                    channels = 1;
                }

                if (rate <= 0 || codec != 0 || channels != 1) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref, "type1-format", block_type, codec);
                }

                if (established_rate == 0)
                    established_rate = rate;

                if (established_rate != rate) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref,
                        "mixed-sample-rates",
                        block_type,
                        codec);
                }

                current_codec = codec;
                frames = block_length - 2;
                pcm = payload + 2;

                if (pass == 0) {
                    total_frames += frames;
                } else if (frames > 0) {
                    memcpy(
                        decoded->pcm + output_position,
                        pcm,
                        frames);
                    output_position += (int)frames;
                }

                saw_audio_data = 1;
                break;
            }

            case 2:
                if (!saw_audio_data || current_codec != 0) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref,
                        "orphan-continuation",
                        block_type,
                        current_codec);
                }

                if (pass == 0) {
                    total_frames += block_length;
                } else if (block_length > 0) {
                    memcpy(
                        decoded->pcm + output_position,
                        payload,
                        block_length);
                    output_position += (int)block_length;
                }
                break;

            case 3:
            {
                Uint32 silence_frames;
                int silence_rate;

                if (block_length < 3) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref, "short-silence", block_type, -1);
                }

                silence_frames =
                    (Uint32)citadel_v12c_u16le(payload) + 1U;
                silence_rate =
                    citadel_v12c_rate_from_tc(payload[2]);

                if (silence_rate <= 0) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref,
                        "bad-silence-rate",
                        block_type,
                        -1);
                }

                if (established_rate == 0)
                    established_rate = silence_rate;

                if (silence_rate != established_rate) {
                    silence_frames = (Uint32)(
                        ((Uint64)silence_frames
                            * (Uint64)established_rate
                            + (Uint64)silence_rate / 2U)
                        / (Uint64)silence_rate);
                }

                if (pass == 0) {
                    total_frames += silence_frames;
                } else if (silence_frames > 0) {
                    memset(
                        decoded->pcm + output_position,
                        128,
                        silence_frames);
                    output_position += (int)silence_frames;
                }
                break;
            }

            case 6:
            case 7:
                ++internal_repeat_markers;
                break;

            case 8:
            {
                Uint16 extended_tc;
                int denominator;
                int mode;

                if (block_length < 4) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref, "short-extended", block_type, -1);
                }

                extended_tc = citadel_v12c_u16le(payload);
                denominator = 65536 - (int)extended_tc;
                mode = (int)payload[3];

                pending_extended_channels = mode + 1;
                pending_extended_codec = (int)payload[2];

                if (denominator <= 0
                    || pending_extended_channels != 1) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref,
                        "extended-format",
                        block_type,
                        pending_extended_codec);
                }

                pending_extended_rate = (int)(
                    256000000U / (Uint32)denominator);
                break;
            }

            case 9:
            {
                Uint32 rate;
                int bits;
                int channels;
                int codec;
                Uint32 frames;
                const Uint8 *pcm;

                if (block_length < 12) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref, "short-type9", block_type, -1);
                }

                rate = citadel_v12c_u32le(payload);
                bits = (int)payload[4];
                channels = (int)payload[5];
                codec = (int)citadel_v12c_u16le(payload + 6);

                if (rate == 0
                    || bits != 8
                    || channels != 1
                    || codec != 0) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref, "type9-format", block_type, codec);
                }

                if (established_rate == 0)
                    established_rate = (int)rate;

                if (established_rate != (int)rate) {
                    citadel_v12c_decoded_clear(decoded);
                    return citadel_v12c_decode_fail(
                        snd_ref,
                        "mixed-sample-rates",
                        block_type,
                        codec);
                }

                current_codec = codec;
                frames = block_length - 12;
                pcm = payload + 12;

                if (pass == 0) {
                    total_frames += frames;
                } else if (frames > 0) {
                    memcpy(
                        decoded->pcm + output_position,
                        pcm,
                        frames);
                    output_position += (int)frames;
                }

                saw_audio_data = 1;
                break;
            }

            default:
                citadel_v12c_decoded_clear(decoded);
                return citadel_v12c_decode_fail(
                    snd_ref, "unknown-block", block_type, -1);
            }

            position += (int)block_length;
        }

        if (pass == 0) {
            if (total_frames == 0 || established_rate <= 0) {
                return citadel_v12c_decode_fail(
                    snd_ref, "no-audio-data", -1, -1);
            }

            decoded->pcm = (Uint8 *)SDL_malloc(total_frames);
            if (decoded->pcm == NULL) {
                return citadel_v12c_decode_fail(
                    snd_ref, "allocation-failed", -1, -1);
            }
        } else if ((Uint32)output_position != total_frames) {
            citadel_v12c_decoded_clear(decoded);
            return citadel_v12c_decode_fail(
                snd_ref, "decode-size-mismatch", -1, -1);
        }
    }

    decoded->frames = total_frames;
    decoded->rate = established_rate;
    decoded->block_mask = block_mask;
    decoded->internal_repeat_markers =
        internal_repeat_markers;

    return OK;
}

static void citadel_v12c_audio_shutdown(void)
{
    int channel;

    if (!citadel_v12c_audio_ready || device == 0)
        return;

    SDL_PauseAudioDevice(device, 1);
    SDL_LockAudioDevice(device);

    for (channel = 0; channel < SND_MAX_SAMPLES; ++channel)
        citadel_v12c_free_voice_locked(channel);

    SDL_UnlockAudioDevice(device);

    citadel_v12c_log(
        "SHUTDOWN device=%u requests=%u started=%u "
        "completed=%u stolen=%u decode_failures=%u",
        (unsigned int)device,
        (unsigned int)citadel_v12c_requests,
        (unsigned int)citadel_v12c_started,
        (unsigned int)citadel_v12c_completed,
        (unsigned int)citadel_v12c_stolen,
        (unsigned int)citadel_v12c_decode_failures);

    SDL_CloseAudioDevice(device);
    device = 0;
    citadel_v12c_audio_ready = false;
}

static int citadel_v12c_open_audio(void)
{
    SDL_AudioSpec wanted;
    int device_count;

    if (citadel_v12c_audio_ready)
        return OK;

    if (citadel_v12c_audio_attempted)
        return ERR_NOEFFECT;

    citadel_v12c_audio_attempted = true;
    remove("AUDIO_3DS_V12C.log");

    SDL_memset(
        citadel_v12c_voices,
        0,
        sizeof(citadel_v12c_voices));

    SDL_memset(
        digi_parms_by_channel,
        0,
        sizeof(digi_parms_by_channel));

    citadel_v12c_log(
        "PROJECT CITADEL AUDIO V12C START build=%s %s "
        "voices=%d",
        __DATE__,
        __TIME__,
        SND_MAX_SAMPLES);

    device_count = SDL_GetNumAudioDevices(0);

    citadel_v12c_log(
        "PLAYBACK device_count=%d first_name=%s",
        device_count,
        device_count > 0 && SDL_GetAudioDeviceName(0, 0) != NULL
            ? SDL_GetAudioDeviceName(0, 0)
            : "(default)");

    SDL_zero(wanted);
    SDL_zero(citadel_v12c_audio_spec);

    wanted.freq = CITADEL_V12C_REQUEST_RATE;
    wanted.format = AUDIO_S16SYS;
    wanted.channels = 2;
    wanted.samples = CITADEL_V12C_REQUEST_SAMPLES;
    wanted.callback = citadel_v12c_audio_callback;
    wanted.userdata = NULL;

    SDL_ClearError();
    device = SDL_OpenAudioDevice(
        NULL,
        0,
        &wanted,
        &citadel_v12c_audio_spec,
        SDL_AUDIO_ALLOW_FREQUENCY_CHANGE
            | SDL_AUDIO_ALLOW_SAMPLES_CHANGE);

    citadel_v12c_log(
        "OPEN device=%u error=\"%s\"",
        (unsigned int)device,
        SDL_GetError());

    if (device == 0) {
        citadel_v12c_log("RESULT FAIL: SDL_OpenAudioDevice");
        return ERR_NOEFFECT;
    }

    citadel_v12c_log(
        "OBTAINED freq=%d format=0x%04X channels=%u "
        "samples=%u size=%u",
        citadel_v12c_audio_spec.freq,
        (unsigned int)citadel_v12c_audio_spec.format,
        (unsigned int)citadel_v12c_audio_spec.channels,
        (unsigned int)citadel_v12c_audio_spec.samples,
        (unsigned int)citadel_v12c_audio_spec.size);

    if (citadel_v12c_audio_spec.format != AUDIO_S16SYS
        || citadel_v12c_audio_spec.channels != 2
        || citadel_v12c_audio_spec.freq <= 0) {
        citadel_v12c_log("RESULT FAIL: expected PCM16 stereo");
        SDL_CloseAudioDevice(device);
        device = 0;
        return ERR_NOEFFECT;
    }

    citadel_v12c_audio_ready = true;
    atexit(citadel_v12c_audio_shutdown);
    SDL_PauseAudioDevice(device, 0);

    citadel_v12c_log(
        "RESULT READY status=%d",
        (int)SDL_GetAudioDeviceStatus(device));

    return OK;
}

static int citadel_v12c_choose_channel_locked(int priority)
{
    int channel;
    int candidate = -1;

    citadel_v12c_reap_finished_locked();

    for (channel = 0; channel < SND_MAX_SAMPLES; ++channel) {
        if (!citadel_v12c_voices[channel].active
            && citadel_v12c_voices[channel].pcm == NULL) {
            return channel;
        }
    }

    for (channel = 0; channel < SND_MAX_SAMPLES; ++channel) {
        if (candidate < 0
            || citadel_v12c_voices[channel].priority
                < citadel_v12c_voices[candidate].priority
            || (citadel_v12c_voices[channel].priority
                    == citadel_v12c_voices[candidate].priority
                && citadel_v12c_voices[channel].serial
                    < citadel_v12c_voices[candidate].serial)) {
            candidate = channel;
        }
    }

    if (candidate >= 0
        && priority >= citadel_v12c_voices[candidate].priority) {
        ++citadel_v12c_stolen;

        if (citadel_v12c_event_logs
            < CITADEL_V12C_EVENT_LOG_LIMIT) {
            ++citadel_v12c_event_logs;
            citadel_v12c_log(
                "STEAL channel=%d old_ref=%d old_pri=%d "
                "new_pri=%d",
                candidate,
                citadel_v12c_voices[candidate].snd_ref,
                citadel_v12c_voices[candidate].priority,
                priority);
        }

        citadel_v12c_free_voice_locked(candidate);
        return candidate;
    }

    return -1;
}

int snd_start_digital(void)
{
    return citadel_v12c_open_audio();
}

int snd_sample_play(
    int snd_ref,
    int len,
    uchar *smp,
    struct snd_digi_parms *dprm)
{
    citadel_v12c_decoded_sound decoded;
    citadel_v12c_voice *voice;
    int channel;
    int priority;
    int loops;

    ++citadel_v12c_requests;

    if (dprm == NULL || smp == NULL || len <= 0)
        return ERR_NOEFFECT;

    if (!citadel_v12c_audio_ready
        && citadel_v12c_open_audio() != OK) {
        return ERR_NOEFFECT;
    }

    if (citadel_v12c_decode_voc(
            snd_ref,
            len,
            (const Uint8 *)smp,
            &decoded) != OK) {
        return ERR_NOEFFECT;
    }

    priority = (int)dprm->pri;
    loops = dprm->loops > 0 ? (int)dprm->loops : -1;

    SDL_LockAudioDevice(device);
    channel = citadel_v12c_choose_channel_locked(priority);

    if (channel < 0) {
        SDL_UnlockAudioDevice(device);
        citadel_v12c_decoded_clear(&decoded);

        if (citadel_v12c_event_logs
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

    return channel;
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
    int old_ref;

    if (hnd_id < 0
        || hnd_id >= SND_MAX_SAMPLES
        || !citadel_v12c_audio_ready
        || device == 0) {
        return;
    }

    SDL_LockAudioDevice(device);
    old_ref = citadel_v12c_voices[hnd_id].snd_ref;
    citadel_v12c_free_voice_locked(hnd_id);
    SDL_UnlockAudioDevice(device);

    if (citadel_v12c_event_logs
        < CITADEL_V12C_EVENT_LOG_LIMIT) {
        ++citadel_v12c_event_logs;
        citadel_v12c_log(
            "END channel=%d ref=%d",
            hnd_id,
            old_ref);
    }
}

void snd_kill_all_samples(void)
{
    int channel;

    if (!citadel_v12c_audio_ready || device == 0)
        return;

    SDL_LockAudioDevice(device);

    for (channel = 0; channel < SND_MAX_SAMPLES; ++channel)
        citadel_v12c_free_voice_locked(channel);

    SDL_UnlockAudioDevice(device);
    citadel_v12c_log("KILL_ALL");
}

snd_digi_parms *snd_sample_parms(int hnd_id)
{
    if (hnd_id < 0 || hnd_id >= SND_MAX_SAMPLES)
        hnd_id = 0;

    if (citadel_v12c_audio_ready
        && device != 0
        && !citadel_v12c_voices[hnd_id].active
        && citadel_v12c_voices[hnd_id].finished) {
        SDL_LockAudioDevice(device);

        if (!citadel_v12c_voices[hnd_id].active
            && citadel_v12c_voices[hnd_id].finished) {
            citadel_v12c_free_voice_locked(hnd_id);
        }

        SDL_UnlockAudioDevice(device);
    }

    return &digi_parms_by_channel[hnd_id];
}

bool snd_sample_playing(int hnd_id)
{
    bool playing;

    if (hnd_id < 0
        || hnd_id >= SND_MAX_SAMPLES
        || !citadel_v12c_audio_ready
        || device == 0) {
        return false;
    }

    SDL_LockAudioDevice(device);
    playing = citadel_v12c_voices[hnd_id].active;

    if (!playing && citadel_v12c_voices[hnd_id].finished)
        citadel_v12c_free_voice_locked(hnd_id);

    SDL_UnlockAudioDevice(device);
    return playing;
}

void snd_sample_reload_parms(snd_digi_parms *sdp)
{
    int channel;
    citadel_v12c_voice *voice;

    if (sdp < digi_parms_by_channel
        || sdp >= digi_parms_by_channel + SND_MAX_SAMPLES
        || !citadel_v12c_audio_ready
        || device == 0) {
        return;
    }

    channel = (int)(sdp - digi_parms_by_channel);

    if (!citadel_v12c_voices[channel].active)
        return;

    SDL_LockAudioDevice(device);
    voice = &citadel_v12c_voices[channel];

    if (voice->active) {
        voice->volume = (int)sdp->vol;
        voice->pan = (int)sdp->pan;
        citadel_v12c_update_gains(voice);
    }

    SDL_UnlockAudioDevice(device);
}

int MacTuneLoadTheme(char *theme_base, int themeID)
{
    (void)theme_base;
    (void)themeID;
    return OK;
}

void MacTuneKillCurrentTheme(void)
{
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

#endif


// Unimplemented sound stubs

void snd_startup(void) {}
int snd_stop_digital(void) { return 1; }
