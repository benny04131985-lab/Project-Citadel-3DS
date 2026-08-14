#include "Citro3DNative.h"

#include <math.h>
#include <string.h>
#include "2d.h"

typedef struct CitadelNativeWorldBuffer {
    CitadelNativeWorldTriangle triangles[
        CITADEL_NATIVE_WORLD_MAX_TRIANGLES];
    size_t count;
    int valid;
} CitadelNativeWorldBuffer;

#define CITADEL_NATIVE_DOOR_MAX_SNAPSHOTS 16u
#define CITADEL_NATIVE_DOOR_MAX_WIDTH     256u
#define CITADEL_NATIVE_DOOR_MAX_HEIGHT    256u
#define CITADEL_NATIVE_DOOR_MAX_PIXELS \
    (CITADEL_NATIVE_DOOR_MAX_WIDTH * CITADEL_NATIVE_DOOR_MAX_HEIGHT)

#define CITADEL_NATIVE_TEXBITMAP_MAX_SNAPSHOTS 16u
#define CITADEL_NATIVE_TEXBITMAP_MAX_WIDTH     256u
#define CITADEL_NATIVE_TEXBITMAP_MAX_HEIGHT    256u
#define CITADEL_NATIVE_TEXBITMAP_MAX_PIXELS \
    (CITADEL_NATIVE_TEXBITMAP_MAX_WIDTH * CITADEL_NATIVE_TEXBITMAP_MAX_HEIGHT)

#define CITADEL_NATIVE_BITMAP_MAX_SNAPSHOTS 32u
#define CITADEL_NATIVE_BITMAP_MAX_WIDTH     256u
#define CITADEL_NATIVE_BITMAP_MAX_HEIGHT    256u
#define CITADEL_NATIVE_BITMAP_MAX_PIXELS \
    (CITADEL_NATIVE_BITMAP_MAX_WIDTH * CITADEL_NATIVE_BITMAP_MAX_HEIGHT)

extern void per_umap(
    grs_bitmap *bitmap,
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info);
extern int h_map(
    grs_bitmap *bitmap,
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info);

typedef struct CitadelNativeDoorTextureSnapshot {
    grs_bitmap bitmap;
    const void *source_bits;
    int source_width;
    int source_height;
    int source_row;
    int source_type;
    unsigned int source_flags;
    uint64_t content_key;
    uint8_t pixels[CITADEL_NATIVE_DOOR_MAX_PIXELS];
    int valid;
} CitadelNativeDoorTextureSnapshot;

typedef struct CitadelNativeTexbitmapTextureSnapshot {
    grs_bitmap bitmap;
    const void *source_bits;
    int source_width;
    int source_height;
    int source_row;
    int source_type;
    unsigned int source_flags;
    uint64_t content_key;
    uint8_t pixels[CITADEL_NATIVE_TEXBITMAP_MAX_PIXELS];
    int valid;
} CitadelNativeTexbitmapTextureSnapshot;

typedef struct CitadelNativeBitmapTextureSnapshot {
    grs_bitmap bitmap;
    int source_width;
    int source_height;
    int texture_width;
    int texture_height;
    unsigned int source_flags;
    uint64_t content_key;
    uint8_t pixels[CITADEL_NATIVE_BITMAP_MAX_PIXELS];
    int valid;
} CitadelNativeBitmapTextureSnapshot;

static CitadelNativeWorldBuffer citadel_native_buffers[2];
static CitadelNativeWorldStats citadel_native_stats;
static CitadelNativeDoorTextureSnapshot
    citadel_native_door_texture_snapshots[
        CITADEL_NATIVE_DOOR_MAX_SNAPSHOTS];
static size_t citadel_native_door_texture_snapshot_count = 0;
static const grs_bitmap *citadel_native_last_door_snapshot = NULL;
static grs_canvas *citadel_native_door_mask_canvas = NULL;
static uint8_t citadel_native_door_mask_source[
    CITADEL_NATIVE_DOOR_MAX_PIXELS];

static CitadelNativeTexbitmapTextureSnapshot
    citadel_native_texbitmap_texture_snapshots[
        CITADEL_NATIVE_TEXBITMAP_MAX_SNAPSHOTS];
static size_t citadel_native_texbitmap_texture_snapshot_count = 0;
static const grs_bitmap *citadel_native_last_texbitmap_snapshot = NULL;
static grs_canvas *citadel_native_texbitmap_mask_canvas = NULL;
static uint8_t citadel_native_texbitmap_mask_source[
    CITADEL_NATIVE_TEXBITMAP_MAX_PIXELS];

static CitadelNativeBitmapTextureSnapshot
    citadel_native_bitmap_texture_snapshots[
        CITADEL_NATIVE_BITMAP_MAX_SNAPSHOTS];
static size_t citadel_native_bitmap_texture_snapshot_count = 0;
static const CitadelNativeBitmapTextureSnapshot *
    citadel_native_last_bitmap_snapshot = NULL;
static size_t citadel_native_last_bitmap_capture_before_count = 0;
static size_t citadel_native_last_bitmap_capture_count = 0;
static int citadel_native_last_bitmap_capture_active = 0;
static int citadel_native_bitmap_category =
    CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
static int citadel_native_last_bitmap_capture_category =
    CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
static grs_canvas *citadel_native_bitmap_mask_canvas = NULL;
static uint8_t citadel_native_bitmap_mask_source[
    CITADEL_NATIVE_BITMAP_MAX_PIXELS];

static int citadel_native_surface_kind =
    CITADEL_NATIVE_SURFACE_NONE;

static int citadel_native_active_eye = 0;
static int citadel_native_engine_frame_open = 0;
static int citadel_native_engine_frame_stereo = 0;
static int citadel_native_engine_frame_split = 0;
static int citadel_native_takeover_active = 0;
static int citadel_native_takeover_present_active = 0;

static grs_canvas *citadel_native_occlusion_canvas = NULL;
static grs_canvas *citadel_native_occlusion_saved_canvas = NULL;
static int citadel_native_occlusion_reference_valid = 0;
static int citadel_native_occlusion_draw_active = 0;

static int citadel_native_viewport_valid;
static int citadel_native_viewport_x = 0;
static int citadel_native_viewport_y = 0;
static int citadel_native_viewport_width = 0;
static int citadel_native_viewport_height = 0;
static int citadel_native_draw_width = 0;
static int citadel_native_draw_height = 0;

static float citadel_native_fix_to_float(fix value)
{
    return (float)value / 65536.0f;
}

static float citadel_native_clamp_light(float value)
{
    if (value < 0.0f)
        return 0.0f;
    if (value > 1.0f)
        return 1.0f;
    return value;
}

static int citadel_native_bitmap_category_is_critter(int category)
{
    return category == CITADEL_NATIVE_BITMAP_CATEGORY_CRITTER;
}

static int citadel_native_bitmap_category_is_multiview(int category)
{
    return category == CITADEL_NATIVE_BITMAP_CATEGORY_MULTIVIEW;
}

static void citadel_native_note_bitmap_category_fallback(
    int category,
    int expected)
{
    if (citadel_native_bitmap_category_is_critter(category)) {
        if (expected)
            ++citadel_native_stats
                .critter_bitmap_expected_software_exclusions;
        else
            ++citadel_native_stats.critter_bitmap_capture_failures;
        return;
    }

    if (citadel_native_bitmap_category_is_multiview(category)) {
        if (expected)
            ++citadel_native_stats
                .multiview_bitmap_expected_software_exclusions;
        else
            ++citadel_native_stats.multiview_bitmap_capture_failures;
    }
}

static void citadel_native_note_bitmap_category_capture(
    int category,
    size_t triangle_count)
{
    if (citadel_native_bitmap_category_is_critter(category)) {
        ++citadel_native_stats.critter_bitmap_polygons_captured;
        citadel_native_stats.critter_bitmap_triangles_captured +=
            triangle_count;
        return;
    }

    if (citadel_native_bitmap_category_is_multiview(category)) {
        ++citadel_native_stats.multiview_bitmap_polygons_captured;
        citadel_native_stats.multiview_bitmap_triangles_captured +=
            triangle_count;
    }
}

static void citadel_native_rollback_bitmap_category_capture(
    int category,
    size_t triangle_count)
{
    if (citadel_native_bitmap_category_is_critter(category)) {
        if (citadel_native_stats.critter_bitmap_polygons_captured > 0)
            --citadel_native_stats.critter_bitmap_polygons_captured;

        if (citadel_native_stats.critter_bitmap_triangles_captured >=
            triangle_count) {
            citadel_native_stats.critter_bitmap_triangles_captured -=
                triangle_count;
        }
        return;
    }

    if (citadel_native_bitmap_category_is_multiview(category)) {
        if (citadel_native_stats.multiview_bitmap_polygons_captured > 0)
            --citadel_native_stats.multiview_bitmap_polygons_captured;

        if (citadel_native_stats.multiview_bitmap_triangles_captured >=
            triangle_count) {
            citadel_native_stats.multiview_bitmap_triangles_captured -=
                triangle_count;
        }
    }
}

static void citadel_native_note_bitmap_category_mask(
    int category)
{
    if (citadel_native_bitmap_category_is_critter(category)) {
        ++citadel_native_stats.critter_bitmap_mask_erases;
        ++citadel_native_stats
            .critter_bitmap_software_calls_suppressed;
        return;
    }

    if (citadel_native_bitmap_category_is_multiview(category)) {
        ++citadel_native_stats.multiview_bitmap_mask_erases;
        ++citadel_native_stats
            .multiview_bitmap_software_calls_suppressed;
    }
}

static void citadel_native_note_bitmap_category_offscreen(
    int category)
{
    if (citadel_native_bitmap_category_is_critter(category)) {
        ++citadel_native_stats.critter_bitmap_offscreen_exclusions;
        ++citadel_native_stats
            .critter_bitmap_software_calls_suppressed;
        return;
    }

    if (citadel_native_bitmap_category_is_multiview(category)) {
        ++citadel_native_stats.multiview_bitmap_offscreen_exclusions;
        ++citadel_native_stats
            .multiview_bitmap_software_calls_suppressed;
    }
}

static int citadel_native_is_power_of_two(unsigned int value)
{
    return value != 0 && (value & (value - 1u)) == 0;
}

static unsigned int citadel_native_bitmap_texture_dimension(int value)
{
    unsigned int result = 8u;

    if (value <= 0 ||
        value > (int)CITADEL_NATIVE_BITMAP_MAX_WIDTH)
        return 0u;

    while (result < (unsigned int)value)
        result <<= 1u;

    return result <= CITADEL_NATIVE_BITMAP_MAX_WIDTH ? result : 0u;
}

static int citadel_native_bitmap_object_source_supported(
    const grs_bitmap *bitmap)
{
    if (bitmap == NULL || bitmap->bits == NULL)
        return 0;

    if (bitmap->type != BMT_FLAT8 && bitmap->type != BMT_RSD8)
        return 0;

    if (bitmap->w <= 0 || bitmap->h <= 0 ||
        bitmap->w > (int)CITADEL_NATIVE_BITMAP_MAX_WIDTH ||
        bitmap->h > (int)CITADEL_NATIVE_BITMAP_MAX_HEIGHT)
        return 0;

    if (bitmap->type == BMT_FLAT8 && bitmap->row < (ushort)bitmap->w)
        return 0;

    return citadel_native_bitmap_texture_dimension(bitmap->w) != 0u &&
           citadel_native_bitmap_texture_dimension(bitmap->h) != 0u;
}

static int citadel_native_bitmap_supported(
    const grs_bitmap *bitmap,
    int allow_transparency)
{
    if (bitmap == NULL || bitmap->bits == NULL)
        return 0;

    if (!allow_transparency && (bitmap->flags & BMF_TRANS))
        return 0;

    if (bitmap->type != BMT_FLAT8 && bitmap->type != BMT_RSD8)
        return 0;

    if (bitmap->w < 8 || bitmap->h < 8 ||
        bitmap->w > 1024 || bitmap->h > 1024)
        return 0;

    if (!citadel_native_is_power_of_two((unsigned int)bitmap->w) ||
        !citadel_native_is_power_of_two((unsigned int)bitmap->h))
        return 0;

    if (bitmap->type == BMT_FLAT8 && bitmap->row < (ushort)bitmap->w)
        return 0;

    return 1;
}

static uint64_t citadel_native_hash_door_pixels(
    const uint8_t *pixels,
    int width,
    int height,
    int row)
{
    uint64_t hash = UINT64_C(1469598103934665603);
    int y;

    if (pixels == NULL || width <= 0 || height <= 0 || row < width)
        return 0;

    for (y = 0; y < height; ++y) {
        const uint8_t *source = pixels + ((size_t)y * (size_t)row);
        int x;

        for (x = 0; x < width; ++x) {
            hash ^= (uint64_t)source[x];
            hash *= UINT64_C(1099511628211);
        }
    }

    hash ^= (uint64_t)(unsigned int)width;
    hash *= UINT64_C(1099511628211);
    hash ^= (uint64_t)(unsigned int)height;
    hash *= UINT64_C(1099511628211);

    return hash != 0 ? hash : UINT64_C(1);
}

static const grs_bitmap *citadel_native_snapshot_door_bitmap(
    const grs_bitmap *source,
    uint64_t *content_key)
{
    CitadelNativeDoorTextureSnapshot *snapshot;
    const uint8_t *source_pixels;
    int source_row;
    uint64_t source_content_key;
    grs_bitmap decoded;
    size_t index;
    int y;

    if (content_key != NULL)
        *content_key = 0;

    if (source == NULL || source->bits == NULL ||
        source->w <= 0 || source->h <= 0 ||
        source->w > (int)CITADEL_NATIVE_DOOR_MAX_WIDTH ||
        source->h > (int)CITADEL_NATIVE_DOOR_MAX_HEIGHT) {
        ++citadel_native_stats.door_texture_snapshot_failures;
        return NULL;
    }

    source_pixels = (const uint8_t *)source->bits;
    source_row = source->row;
    memset(&decoded, 0, sizeof(decoded));

    if (source->type == BMT_RSD8) {
        if (gr_rsd8_convert((grs_bitmap *)source, &decoded) != 0 ||
            decoded.bits == NULL) {
            ++citadel_native_stats.door_texture_snapshot_failures;
            return NULL;
        }

        source_pixels = (const uint8_t *)decoded.bits;
        source_row = decoded.row >= (ushort)source->w
            ? decoded.row
            : source->w;
    } else if (source->type != BMT_FLAT8 || source_row < source->w) {
        ++citadel_native_stats.door_texture_snapshot_failures;
        return NULL;
    }

    source_content_key = citadel_native_hash_door_pixels(
        source_pixels,
        source->w,
        source->h,
        source_row);

    if (source_content_key == 0) {
        ++citadel_native_stats.door_texture_snapshot_failures;
        return NULL;
    }

    /*
     * Resource locks may recycle the same bits address for different door
     * frames. Reuse only after comparing decoded content, not pointer identity.
     */
    for (index = 0;
         index < citadel_native_door_texture_snapshot_count;
         ++index) {
        snapshot = &citadel_native_door_texture_snapshots[index];

        if (snapshot->valid &&
            snapshot->source_width == source->w &&
            snapshot->source_height == source->h &&
            snapshot->source_flags == (unsigned int)source->flags &&
            snapshot->content_key == source_content_key) {
            ++citadel_native_stats.door_texture_snapshot_reuses;
            if (content_key != NULL)
                *content_key = snapshot->content_key;
            return &snapshot->bitmap;
        }
    }

    if (citadel_native_door_texture_snapshot_count >=
        CITADEL_NATIVE_DOOR_MAX_SNAPSHOTS) {
        ++citadel_native_stats.door_texture_snapshot_failures;
        return NULL;
    }

    snapshot = &citadel_native_door_texture_snapshots[
        citadel_native_door_texture_snapshot_count++];
    memset(snapshot, 0, sizeof(*snapshot));

    for (y = 0; y < source->h; ++y) {
        memcpy(
            snapshot->pixels + ((size_t)y * (size_t)source->w),
            source_pixels + ((size_t)y * (size_t)source_row),
            (size_t)source->w);
    }

    snapshot->bitmap = *source;
    snapshot->bitmap.bits = snapshot->pixels;
    snapshot->bitmap.type = BMT_FLAT8;
    snapshot->bitmap.row = (ushort)source->w;
    snapshot->source_bits = source->bits;
    snapshot->source_width = source->w;
    snapshot->source_height = source->h;
    snapshot->source_row = source->row;
    snapshot->source_type = source->type;
    snapshot->source_flags = (unsigned int)source->flags;
    snapshot->content_key = source_content_key;
    snapshot->valid = 1;

    ++citadel_native_stats.door_texture_snapshots;

    if (content_key != NULL)
        *content_key = snapshot->content_key;

    return &snapshot->bitmap;
}

static const grs_bitmap *citadel_native_snapshot_texbitmap(
    const grs_bitmap *source,
    uint64_t *content_key)
{
    CitadelNativeTexbitmapTextureSnapshot *snapshot;
    const uint8_t *source_pixels;
    int source_row;
    uint64_t source_content_key;
    grs_bitmap decoded;
    size_t index;
    int y;

    if (content_key != NULL)
        *content_key = 0;

    if (source == NULL || source->bits == NULL ||
        source->w <= 0 || source->h <= 0 ||
        source->w > (int)CITADEL_NATIVE_TEXBITMAP_MAX_WIDTH ||
        source->h > (int)CITADEL_NATIVE_TEXBITMAP_MAX_HEIGHT) {
        ++citadel_native_stats.texbitmap_texture_snapshot_failures;
        return NULL;
    }

    source_pixels = (const uint8_t *)source->bits;
    source_row = source->row;
    memset(&decoded, 0, sizeof(decoded));

    if (source->type == BMT_RSD8) {
        if (gr_rsd8_convert((grs_bitmap *)source, &decoded) != 0 ||
            decoded.bits == NULL) {
            ++citadel_native_stats.texbitmap_texture_snapshot_failures;
            return NULL;
        }

        source_pixels = (const uint8_t *)decoded.bits;
        source_row = decoded.row >= (ushort)source->w
            ? decoded.row
            : source->w;
    } else if (source->type != BMT_FLAT8 || source_row < source->w) {
        ++citadel_native_stats.texbitmap_texture_snapshot_failures;
        return NULL;
    }

    source_content_key = citadel_native_hash_door_pixels(
        source_pixels,
        source->w,
        source->h,
        source_row);

    if (source_content_key == 0) {
        ++citadel_native_stats.texbitmap_texture_snapshot_failures;
        return NULL;
    }

    for (index = 0;
         index < citadel_native_texbitmap_texture_snapshot_count;
         ++index) {
        snapshot = &citadel_native_texbitmap_texture_snapshots[index];

        if (snapshot->valid &&
            snapshot->source_width == source->w &&
            snapshot->source_height == source->h &&
            snapshot->source_flags == (unsigned int)source->flags &&
            snapshot->content_key == source_content_key) {
            ++citadel_native_stats.texbitmap_texture_snapshot_reuses;
            if (content_key != NULL)
                *content_key = snapshot->content_key;
            return &snapshot->bitmap;
        }
    }

    if (citadel_native_texbitmap_texture_snapshot_count >=
        CITADEL_NATIVE_TEXBITMAP_MAX_SNAPSHOTS) {
        ++citadel_native_stats.texbitmap_texture_snapshot_failures;
        return NULL;
    }

    snapshot = &citadel_native_texbitmap_texture_snapshots[
        citadel_native_texbitmap_texture_snapshot_count++];
    memset(snapshot, 0, sizeof(*snapshot));

    for (y = 0; y < source->h; ++y) {
        memcpy(
            snapshot->pixels + ((size_t)y * (size_t)source->w),
            source_pixels + ((size_t)y * (size_t)source_row),
            (size_t)source->w);
    }

    snapshot->bitmap = *source;
    snapshot->bitmap.bits = snapshot->pixels;
    snapshot->bitmap.type = BMT_FLAT8;
    snapshot->bitmap.row = (ushort)source->w;
    snapshot->source_bits = source->bits;
    snapshot->source_width = source->w;
    snapshot->source_height = source->h;
    snapshot->source_row = source->row;
    snapshot->source_type = source->type;
    snapshot->source_flags = (unsigned int)source->flags;
    snapshot->content_key = source_content_key;
    snapshot->valid = 1;

    ++citadel_native_stats.texbitmap_texture_snapshots;

    if (content_key != NULL)
        *content_key = snapshot->content_key;

    return &snapshot->bitmap;
}

static const CitadelNativeBitmapTextureSnapshot *
citadel_native_snapshot_bitmap_object(
    const grs_bitmap *source,
    uint64_t *content_key)
{
    CitadelNativeBitmapTextureSnapshot *snapshot;
    const uint8_t *source_pixels;
    int source_row;
    int texture_width;
    int texture_height;
    uint64_t source_content_key;
    grs_bitmap decoded;
    size_t index;
    int y;

    if (content_key != NULL)
        *content_key = 0;

    if (!citadel_native_bitmap_object_source_supported(source)) {
        ++citadel_native_stats.bitmap_object_texture_snapshot_failures;
        return NULL;
    }

    texture_width =
        (int)citadel_native_bitmap_texture_dimension(source->w);
    texture_height =
        (int)citadel_native_bitmap_texture_dimension(source->h);

    if (texture_width <= 0 || texture_height <= 0) {
        ++citadel_native_stats.bitmap_object_texture_snapshot_failures;
        return NULL;
    }

    source_pixels = (const uint8_t *)source->bits;
    source_row = source->row;
    memset(&decoded, 0, sizeof(decoded));

    if (source->type == BMT_RSD8) {
        if (gr_rsd8_convert((grs_bitmap *)source, &decoded) != 0 ||
            decoded.bits == NULL) {
            ++citadel_native_stats.bitmap_object_texture_snapshot_failures;
            return NULL;
        }

        source_pixels = (const uint8_t *)decoded.bits;
        source_row = decoded.row >= (ushort)source->w
            ? decoded.row
            : source->w;
    } else if (source->type != BMT_FLAT8 || source_row < source->w) {
        ++citadel_native_stats.bitmap_object_texture_snapshot_failures;
        return NULL;
    }

    source_content_key = citadel_native_hash_door_pixels(
        source_pixels,
        source->w,
        source->h,
        source_row);

    if (source_content_key == 0) {
        ++citadel_native_stats.bitmap_object_texture_snapshot_failures;
        return NULL;
    }

    for (index = 0;
         index < citadel_native_bitmap_texture_snapshot_count;
         ++index) {
        snapshot = &citadel_native_bitmap_texture_snapshots[index];

        if (snapshot->valid &&
            snapshot->source_width == source->w &&
            snapshot->source_height == source->h &&
            snapshot->texture_width == texture_width &&
            snapshot->texture_height == texture_height &&
            snapshot->source_flags == (unsigned int)source->flags &&
            snapshot->content_key == source_content_key) {
            ++citadel_native_stats.bitmap_object_texture_snapshot_reuses;
            if (content_key != NULL)
                *content_key = snapshot->content_key;
            return snapshot;
        }
    }

    if (citadel_native_bitmap_texture_snapshot_count >=
        CITADEL_NATIVE_BITMAP_MAX_SNAPSHOTS) {
        ++citadel_native_stats.bitmap_object_texture_snapshot_failures;
        return NULL;
    }

    snapshot = &citadel_native_bitmap_texture_snapshots[
        citadel_native_bitmap_texture_snapshot_count++];
    memset(snapshot, 0, sizeof(*snapshot));

    memset(
        snapshot->pixels,
        0,
        (size_t)texture_width *
            (size_t)texture_height *
            sizeof(snapshot->pixels[0]));

    for (y = 0; y < source->h; ++y) {
        memcpy(
            snapshot->pixels +
                ((size_t)y * (size_t)texture_width),
            source_pixels +
                ((size_t)y * (size_t)source_row),
            (size_t)source->w);
    }

    snapshot->bitmap = *source;
    snapshot->bitmap.bits = snapshot->pixels;
    snapshot->bitmap.type = BMT_FLAT8;
    snapshot->bitmap.row = (ushort)texture_width;
    snapshot->bitmap.w = (short)texture_width;
    snapshot->bitmap.h = (short)texture_height;
    snapshot->bitmap.flags |= BMF_TRANS;
    snapshot->source_width = source->w;
    snapshot->source_height = source->h;
    snapshot->texture_width = texture_width;
    snapshot->texture_height = texture_height;
    snapshot->source_flags = (unsigned int)source->flags;
    snapshot->content_key = source_content_key;
    snapshot->valid = 1;

    ++citadel_native_stats.bitmap_object_texture_snapshots;

    if (source->w != texture_width ||
        source->h != texture_height) {
        ++citadel_native_stats.bitmap_object_padded_texture_snapshots;
        citadel_native_stats.bitmap_object_padding_texels +=
            (uint64_t)(
                (texture_width * texture_height) -
                (source->w * source->h));
    }

    if (content_key != NULL)
        *content_key = snapshot->content_key;

    return snapshot;
}

static int citadel_native_fix_floor_to_int(fix value)
{
    if (value >= 0)
        return (int)(value >> 16);

    return -(int)(((-value) + 0xFFFF) >> 16);
}

static int citadel_native_fix_ceil_to_int(fix value)
{
    if (value >= 0)
        return (int)((value + 0xFFFF) >> 16);

    return -(int)((-value) >> 16);
}

int citadel_native_world_apply_transparent_door_erase(
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info)
{
    grs_canvas *saved_canvas = grd_canvas;
    grs_bitmap mask_bitmap;
    grs_tmap_info mask_info;
    const uint8_t *source_pixels;
    uint8_t *mask_canvas_pixels;
    uint8_t *destination_pixels;
    int min_x;
    int min_y;
    int max_x;
    int max_y;
    int source_row;
    int y;
    int index;
    uint64_t erased_pixels = 0;

    if (saved_canvas == NULL || saved_canvas->bm.bits == NULL ||
        saved_canvas->bm.type != BMT_FLAT8 ||
        citadel_native_last_door_snapshot == NULL ||
        citadel_native_last_door_snapshot->bits == NULL ||
        n < 3 || vertices == NULL || info == NULL) {
        ++citadel_native_stats.transparent_door_mask_failures;
        return 0;
    }

    if (citadel_native_door_mask_canvas == NULL ||
        citadel_native_door_mask_canvas->bm.w != saved_canvas->bm.w ||
        citadel_native_door_mask_canvas->bm.h != saved_canvas->bm.h) {
        if (citadel_native_door_mask_canvas != NULL)
            gr_free_canvas(citadel_native_door_mask_canvas);

        citadel_native_door_mask_canvas = gr_alloc_canvas(
            BMT_FLAT8,
            saved_canvas->bm.w,
            saved_canvas->bm.h);
    }

    if (citadel_native_door_mask_canvas == NULL ||
        citadel_native_door_mask_canvas->bm.bits == NULL) {
        ++citadel_native_stats.transparent_door_mask_failures;
        return 0;
    }

    source_pixels = (const uint8_t *)
        citadel_native_last_door_snapshot->bits;
    source_row = citadel_native_last_door_snapshot->row;

    if (source_row < citadel_native_last_door_snapshot->w ||
        citadel_native_last_door_snapshot->w <= 0 ||
        citadel_native_last_door_snapshot->h <= 0 ||
        citadel_native_last_door_snapshot->w >
            (int)CITADEL_NATIVE_DOOR_MAX_WIDTH ||
        citadel_native_last_door_snapshot->h >
            (int)CITADEL_NATIVE_DOOR_MAX_HEIGHT) {
        ++citadel_native_stats.transparent_door_mask_failures;
        return 0;
    }

    for (y = 0; y < citadel_native_last_door_snapshot->h; ++y) {
        int x;
        const uint8_t *source_row_pixels =
            source_pixels + ((size_t)y * (size_t)source_row);
        uint8_t *mask_source_row =
            citadel_native_door_mask_source +
            ((size_t)y *
             (size_t)citadel_native_last_door_snapshot->w);

        for (x = 0;
             x < citadel_native_last_door_snapshot->w;
             ++x) {
            mask_source_row[x] = source_row_pixels[x] == 0 ? 0 : 1;
        }
    }

    min_x = max_x = citadel_native_fix_floor_to_int(vertices[0]->x);
    min_y = max_y = citadel_native_fix_floor_to_int(vertices[0]->y);

    for (index = 1; index < n; ++index) {
        const int vertex_min_x =
            citadel_native_fix_floor_to_int(vertices[index]->x);
        const int vertex_min_y =
            citadel_native_fix_floor_to_int(vertices[index]->y);
        const int vertex_max_x =
            citadel_native_fix_ceil_to_int(vertices[index]->x);
        const int vertex_max_y =
            citadel_native_fix_ceil_to_int(vertices[index]->y);

        if (vertex_min_x < min_x)
            min_x = vertex_min_x;
        if (vertex_min_y < min_y)
            min_y = vertex_min_y;
        if (vertex_max_x > max_x)
            max_x = vertex_max_x;
        if (vertex_max_y > max_y)
            max_y = vertex_max_y;
    }

    min_x -= 2;
    min_y -= 2;
    max_x += 2;
    max_y += 2;

    if (min_x < 0)
        min_x = 0;
    if (min_y < 0)
        min_y = 0;
    if (max_x >= saved_canvas->bm.w)
        max_x = saved_canvas->bm.w - 1;
    if (max_y >= saved_canvas->bm.h)
        max_y = saved_canvas->bm.h - 1;

    if (min_x > max_x || min_y > max_y) {
        ++citadel_native_stats.transparent_door_mask_failures;
        return 0;
    }

    citadel_native_door_mask_canvas->gc = saved_canvas->gc;
    mask_canvas_pixels =
        (uint8_t *)citadel_native_door_mask_canvas->bm.bits;

    for (y = min_y; y <= max_y; ++y) {
        memset(
            mask_canvas_pixels +
                ((size_t)y *
                 (size_t)citadel_native_door_mask_canvas->bm.row) +
                (size_t)min_x,
            0,
            (size_t)(max_x - min_x + 1));
    }

    mask_bitmap = *citadel_native_last_door_snapshot;
    mask_bitmap.bits = citadel_native_door_mask_source;
    mask_bitmap.type = BMT_FLAT8;
    mask_bitmap.row = (ushort)mask_bitmap.w;
    mask_bitmap.flags |= BMF_TRANS;

    mask_info = *info;
    mask_info.tmap_type = GRC_PER;
    mask_info.flags = 0;
    mask_info.clut = NULL;

    gr_set_canvas(citadel_native_door_mask_canvas);
    per_umap(&mask_bitmap, n, vertices, &mask_info);
    gr_set_canvas(saved_canvas);

    destination_pixels = (uint8_t *)saved_canvas->bm.bits;

    for (y = min_y; y <= max_y; ++y) {
        uint8_t *mask_row =
            mask_canvas_pixels +
            ((size_t)y *
             (size_t)citadel_native_door_mask_canvas->bm.row);
        uint8_t *destination_row =
            destination_pixels +
            ((size_t)y * (size_t)saved_canvas->bm.row);
        int x;

        for (x = min_x; x <= max_x; ++x) {
            if (mask_row[x] != 0) {
                destination_row[x] = 0;
                ++erased_pixels;
            }
        }
    }

    ++citadel_native_stats.transparent_door_mask_erases;
    ++citadel_native_stats.software_door_calls_suppressed;
    citadel_native_stats.transparent_door_mask_pixels_erased +=
        erased_pixels;
    return 1;
}


int citadel_native_world_apply_transparent_texbitmap_erase(
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info)
{
    grs_canvas *saved_canvas = grd_canvas;
    grs_bitmap mask_bitmap;
    grs_tmap_info mask_info;
    const uint8_t *source_pixels;
    uint8_t *mask_canvas_pixels;
    uint8_t *destination_pixels;
    int min_x;
    int min_y;
    int max_x;
    int max_y;
    int source_row;
    int y;
    int index;
    uint64_t erased_pixels = 0;

    if (saved_canvas == NULL || saved_canvas->bm.bits == NULL ||
        saved_canvas->bm.type != BMT_FLAT8 ||
        citadel_native_last_texbitmap_snapshot == NULL ||
        citadel_native_last_texbitmap_snapshot->bits == NULL ||
        n < 3 || vertices == NULL || info == NULL) {
        ++citadel_native_stats.texbitmap_mask_failures;
        ++citadel_native_stats.texbitmap_software_fallbacks;
        return 0;
    }

    if (citadel_native_texbitmap_mask_canvas == NULL ||
        citadel_native_texbitmap_mask_canvas->bm.w != saved_canvas->bm.w ||
        citadel_native_texbitmap_mask_canvas->bm.h != saved_canvas->bm.h) {
        if (citadel_native_texbitmap_mask_canvas != NULL)
            gr_free_canvas(citadel_native_texbitmap_mask_canvas);

        citadel_native_texbitmap_mask_canvas = gr_alloc_canvas(
            BMT_FLAT8,
            saved_canvas->bm.w,
            saved_canvas->bm.h);
    }

    if (citadel_native_texbitmap_mask_canvas == NULL ||
        citadel_native_texbitmap_mask_canvas->bm.bits == NULL) {
        ++citadel_native_stats.texbitmap_mask_failures;
        ++citadel_native_stats.texbitmap_software_fallbacks;
        return 0;
    }

    source_pixels =
        (const uint8_t *)citadel_native_last_texbitmap_snapshot->bits;
    source_row = citadel_native_last_texbitmap_snapshot->row;

    if (source_row < citadel_native_last_texbitmap_snapshot->w ||
        citadel_native_last_texbitmap_snapshot->w <= 0 ||
        citadel_native_last_texbitmap_snapshot->h <= 0 ||
        citadel_native_last_texbitmap_snapshot->w >
            (int)CITADEL_NATIVE_TEXBITMAP_MAX_WIDTH ||
        citadel_native_last_texbitmap_snapshot->h >
            (int)CITADEL_NATIVE_TEXBITMAP_MAX_HEIGHT) {
        ++citadel_native_stats.texbitmap_mask_failures;
        ++citadel_native_stats.texbitmap_software_fallbacks;
        return 0;
    }

    for (y = 0; y < citadel_native_last_texbitmap_snapshot->h; ++y) {
        int x;
        const uint8_t *source_row_pixels =
            source_pixels + ((size_t)y * (size_t)source_row);
        uint8_t *mask_source_row =
            citadel_native_texbitmap_mask_source +
            ((size_t)y *
             (size_t)citadel_native_last_texbitmap_snapshot->w);

        for (x = 0;
             x < citadel_native_last_texbitmap_snapshot->w;
             ++x) {
            mask_source_row[x] = source_row_pixels[x] == 0 ? 0 : 1;
        }
    }

    min_x = max_x = citadel_native_fix_floor_to_int(vertices[0]->x);
    min_y = max_y = citadel_native_fix_floor_to_int(vertices[0]->y);

    for (index = 1; index < n; ++index) {
        const int vertex_min_x =
            citadel_native_fix_floor_to_int(vertices[index]->x);
        const int vertex_min_y =
            citadel_native_fix_floor_to_int(vertices[index]->y);
        const int vertex_max_x =
            citadel_native_fix_ceil_to_int(vertices[index]->x);
        const int vertex_max_y =
            citadel_native_fix_ceil_to_int(vertices[index]->y);

        if (vertex_min_x < min_x)
            min_x = vertex_min_x;
        if (vertex_min_y < min_y)
            min_y = vertex_min_y;
        if (vertex_max_x > max_x)
            max_x = vertex_max_x;
        if (vertex_max_y > max_y)
            max_y = vertex_max_y;
    }

    min_x -= 2;
    min_y -= 2;
    max_x += 2;
    max_y += 2;

    if (min_x < 0)
        min_x = 0;
    if (min_y < 0)
        min_y = 0;
    if (max_x >= saved_canvas->bm.w)
        max_x = saved_canvas->bm.w - 1;
    if (max_y >= saved_canvas->bm.h)
        max_y = saved_canvas->bm.h - 1;

    if (min_x > max_x || min_y > max_y) {
        ++citadel_native_stats.texbitmap_mask_failures;
        ++citadel_native_stats.texbitmap_software_fallbacks;
        return 0;
    }

    citadel_native_texbitmap_mask_canvas->gc = saved_canvas->gc;
    mask_canvas_pixels =
        (uint8_t *)citadel_native_texbitmap_mask_canvas->bm.bits;

    for (y = min_y; y <= max_y; ++y) {
        memset(
            mask_canvas_pixels +
                ((size_t)y *
                 (size_t)citadel_native_texbitmap_mask_canvas->bm.row) +
                (size_t)min_x,
            0,
            (size_t)(max_x - min_x + 1));
    }

    mask_bitmap = *citadel_native_last_texbitmap_snapshot;
    mask_bitmap.bits = citadel_native_texbitmap_mask_source;
    mask_bitmap.type = BMT_FLAT8;
    mask_bitmap.row = (ushort)mask_bitmap.w;
    mask_bitmap.flags |= BMF_TRANS;

    mask_info = *info;
    mask_info.tmap_type = GRC_PER;
    mask_info.flags = 0;
    mask_info.clut = NULL;

    gr_set_canvas(citadel_native_texbitmap_mask_canvas);
    per_umap(&mask_bitmap, n, vertices, &mask_info);
    gr_set_canvas(saved_canvas);

    destination_pixels = (uint8_t *)saved_canvas->bm.bits;

    for (y = min_y; y <= max_y; ++y) {
        uint8_t *mask_row =
            mask_canvas_pixels +
            ((size_t)y *
             (size_t)citadel_native_texbitmap_mask_canvas->bm.row);
        uint8_t *destination_row =
            destination_pixels +
            ((size_t)y * (size_t)saved_canvas->bm.row);
        int x;

        for (x = min_x; x <= max_x; ++x) {
            if (mask_row[x] != 0) {
                destination_row[x] = 0;
                ++erased_pixels;
            }
        }
    }

    ++citadel_native_stats.texbitmap_mask_erases;
    ++citadel_native_stats.texbitmap_software_calls_suppressed;
    citadel_native_stats.texbitmap_mask_pixels_erased += erased_pixels;
    return 1;
}

int citadel_native_world_apply_transparent_bitmap_erase(
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info)
{
    grs_canvas *saved_canvas = grd_canvas;
    grs_bitmap mask_bitmap;
    grs_tmap_info mask_info;
    const uint8_t *source_pixels;
    uint8_t *mask_canvas_pixels;
    uint8_t *destination_pixels;
    CitadelNativeWorldBuffer *buffer;
    int min_x;
    int min_y;
    int max_x;
    int max_y;
    int source_row;
    int y;
    int index;
    uint64_t erased_pixels = 0;

    if (saved_canvas == NULL || saved_canvas->bm.bits == NULL ||
        saved_canvas->bm.type != BMT_FLAT8 ||
        citadel_native_last_bitmap_snapshot == NULL ||
        citadel_native_last_bitmap_snapshot->bitmap.bits == NULL ||
        n != 4 || vertices == NULL || info == NULL) {
        ++citadel_native_stats.bitmap_object_mask_state_failures;
        ++citadel_native_stats.bitmap_object_mask_failures;
        return 0;
    }

    if (citadel_native_bitmap_mask_canvas == NULL ||
        citadel_native_bitmap_mask_canvas->bm.w != saved_canvas->bm.w ||
        citadel_native_bitmap_mask_canvas->bm.h != saved_canvas->bm.h) {
        if (citadel_native_bitmap_mask_canvas != NULL)
            gr_free_canvas(citadel_native_bitmap_mask_canvas);

        citadel_native_bitmap_mask_canvas = gr_alloc_canvas(
            BMT_FLAT8,
            saved_canvas->bm.w,
            saved_canvas->bm.h);
    }

    if (citadel_native_bitmap_mask_canvas == NULL ||
        citadel_native_bitmap_mask_canvas->bm.bits == NULL) {
        ++citadel_native_stats.bitmap_object_mask_canvas_failures;
        ++citadel_native_stats.bitmap_object_mask_failures;
        return 0;
    }

    source_pixels = (const uint8_t *)
        citadel_native_last_bitmap_snapshot->bitmap.bits;
    source_row = citadel_native_last_bitmap_snapshot->bitmap.row;

    if (source_row <
            citadel_native_last_bitmap_snapshot->source_width ||
        citadel_native_last_bitmap_snapshot->source_width <= 0 ||
        citadel_native_last_bitmap_snapshot->source_height <= 0 ||
        citadel_native_last_bitmap_snapshot->source_width >
            (int)CITADEL_NATIVE_BITMAP_MAX_WIDTH ||
        citadel_native_last_bitmap_snapshot->source_height >
            (int)CITADEL_NATIVE_BITMAP_MAX_HEIGHT) {
        ++citadel_native_stats.bitmap_object_mask_source_failures;
        ++citadel_native_stats.bitmap_object_mask_failures;
        return 0;
    }

    for (y = 0;
         y < citadel_native_last_bitmap_snapshot->source_height;
         ++y) {
        int x;
        const uint8_t *source_row_pixels =
            source_pixels + ((size_t)y * (size_t)source_row);
        uint8_t *mask_source_row =
            citadel_native_bitmap_mask_source +
            ((size_t)y * (size_t)source_row);

        for (x = 0;
             x < citadel_native_last_bitmap_snapshot->source_width;
             ++x) {
            mask_source_row[x] = source_row_pixels[x] == 0 ? 0 : 1;
        }
    }

    min_x = max_x = citadel_native_fix_floor_to_int(vertices[0]->x);
    min_y = max_y = citadel_native_fix_floor_to_int(vertices[0]->y);

    for (index = 1; index < n; ++index) {
        const int vertex_min_x =
            citadel_native_fix_floor_to_int(vertices[index]->x);
        const int vertex_min_y =
            citadel_native_fix_floor_to_int(vertices[index]->y);
        const int vertex_max_x =
            citadel_native_fix_ceil_to_int(vertices[index]->x);
        const int vertex_max_y =
            citadel_native_fix_ceil_to_int(vertices[index]->y);

        if (vertex_min_x < min_x)
            min_x = vertex_min_x;
        if (vertex_min_y < min_y)
            min_y = vertex_min_y;
        if (vertex_max_x > max_x)
            max_x = vertex_max_x;
        if (vertex_max_y > max_y)
            max_y = vertex_max_y;
    }

    min_x -= 2;
    min_y -= 2;
    max_x += 2;
    max_y += 2;

    if (min_x < 0)
        min_x = 0;
    if (min_y < 0)
        min_y = 0;
    if (max_x >= saved_canvas->bm.w)
        max_x = saved_canvas->bm.w - 1;
    if (max_y >= saved_canvas->bm.h)
        max_y = saved_canvas->bm.h - 1;

    if (min_x > max_x || min_y > max_y) {
        /*
         * R3D5B1E: this quad lies entirely outside the active software
         * foreground canvas. The software mapper would touch no pixels, and
         * the final GPU viewport would clip the native quad as well.
         *
         * Remove the already-queued native triangles, suppress the equally
         * no-op software mapper call, and count an expected visibility
         * exclusion rather than a capture or mask failure.
         */
        buffer = &citadel_native_buffers[citadel_native_active_eye];

        if (!citadel_native_last_bitmap_capture_active ||
            !buffer->valid ||
            buffer->count <
                citadel_native_last_bitmap_capture_before_count +
                citadel_native_last_bitmap_capture_count) {
            ++citadel_native_stats.bitmap_object_mask_state_failures;
            ++citadel_native_stats.bitmap_object_mask_failures;
            return 0;
        }

        buffer->count =
            citadel_native_last_bitmap_capture_before_count;

        if (citadel_native_stats.bitmap_object_polygons_captured > 0)
            --citadel_native_stats.bitmap_object_polygons_captured;

        if (citadel_native_stats.bitmap_object_triangles_captured >=
            citadel_native_last_bitmap_capture_count) {
            citadel_native_stats.bitmap_object_triangles_captured -=
                citadel_native_last_bitmap_capture_count;
        }

        if (citadel_native_stats.textured_polygons_captured > 0)
            --citadel_native_stats.textured_polygons_captured;

        citadel_native_rollback_bitmap_category_capture(
            citadel_native_last_bitmap_capture_category,
            citadel_native_last_bitmap_capture_count);
        citadel_native_note_bitmap_category_offscreen(
            citadel_native_last_bitmap_capture_category);

        ++citadel_native_stats.bitmap_object_offscreen_exclusions;
        ++citadel_native_stats.bitmap_object_software_calls_suppressed;

        citadel_native_last_bitmap_snapshot = NULL;
        citadel_native_last_bitmap_capture_before_count = 0;
        citadel_native_last_bitmap_capture_count = 0;
        citadel_native_last_bitmap_capture_active = 0;
        citadel_native_last_bitmap_capture_category =
            CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
        return 1;
    }

    citadel_native_bitmap_mask_canvas->gc = saved_canvas->gc;
    mask_canvas_pixels =
        (uint8_t *)citadel_native_bitmap_mask_canvas->bm.bits;

    for (y = min_y; y <= max_y; ++y) {
        memset(
            mask_canvas_pixels +
                ((size_t)y *
                 (size_t)citadel_native_bitmap_mask_canvas->bm.row) +
                (size_t)min_x,
            0,
            (size_t)(max_x - min_x + 1));
    }

    mask_bitmap = citadel_native_last_bitmap_snapshot->bitmap;
    mask_bitmap.bits = citadel_native_bitmap_mask_source;
    mask_bitmap.type = BMT_FLAT8;
    mask_bitmap.row =
        (ushort)citadel_native_last_bitmap_snapshot->texture_width;
    mask_bitmap.w =
        (short)citadel_native_last_bitmap_snapshot->source_width;
    mask_bitmap.h =
        (short)citadel_native_last_bitmap_snapshot->source_height;
    mask_bitmap.flags |= BMF_TRANS;

    mask_info = *info;
    mask_info.tmap_type = GRC_BILIN;
    mask_info.flags = 0;
    mask_info.clut = NULL;

    gr_set_canvas(citadel_native_bitmap_mask_canvas);
    h_map(&mask_bitmap, n, vertices, &mask_info);
    gr_set_canvas(saved_canvas);

    destination_pixels = (uint8_t *)saved_canvas->bm.bits;

    for (y = min_y; y <= max_y; ++y) {
        uint8_t *mask_row =
            mask_canvas_pixels +
            ((size_t)y *
             (size_t)citadel_native_bitmap_mask_canvas->bm.row);
        uint8_t *destination_row =
            destination_pixels +
            ((size_t)y * (size_t)saved_canvas->bm.row);
        int x;

        for (x = min_x; x <= max_x; ++x) {
            if (mask_row[x] != 0) {
                destination_row[x] = 0;
                ++erased_pixels;
            }
        }
    }

    ++citadel_native_stats.bitmap_object_mask_erases;
    ++citadel_native_stats.bitmap_object_software_calls_suppressed;
    citadel_native_stats.bitmap_object_mask_pixels_erased += erased_pixels;
    citadel_native_note_bitmap_category_mask(
        citadel_native_last_bitmap_capture_category);
    citadel_native_last_bitmap_capture_active = 0;
    citadel_native_last_bitmap_capture_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
    return 1;
}

void citadel_native_world_cancel_bitmap_capture(void)
{
    CitadelNativeWorldBuffer *buffer;

    if (!citadel_native_last_bitmap_capture_active)
        return;

    buffer = &citadel_native_buffers[citadel_native_active_eye];

    if (buffer->valid &&
        buffer->count >=
            citadel_native_last_bitmap_capture_before_count +
            citadel_native_last_bitmap_capture_count) {
        buffer->count = citadel_native_last_bitmap_capture_before_count;
    }

    if (citadel_native_stats.bitmap_object_polygons_captured > 0)
        --citadel_native_stats.bitmap_object_polygons_captured;

    if (citadel_native_stats.bitmap_object_triangles_captured >=
        citadel_native_last_bitmap_capture_count) {
        citadel_native_stats.bitmap_object_triangles_captured -=
            citadel_native_last_bitmap_capture_count;
    }

    if (citadel_native_stats.textured_polygons_captured > 0)
        --citadel_native_stats.textured_polygons_captured;

    citadel_native_rollback_bitmap_category_capture(
        citadel_native_last_bitmap_capture_category,
        citadel_native_last_bitmap_capture_count);
    citadel_native_note_bitmap_category_fallback(
        citadel_native_last_bitmap_capture_category,
        0);

    ++citadel_native_stats.bitmap_object_capture_fallbacks;
    ++citadel_native_stats.bitmap_object_software_fallbacks;
    citadel_native_last_bitmap_snapshot = NULL;
    citadel_native_last_bitmap_capture_before_count = 0;
    citadel_native_last_bitmap_capture_count = 0;
    citadel_native_last_bitmap_capture_active = 0;
    citadel_native_last_bitmap_capture_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
}

static CitadelNativeWorldBuffer *
citadel_native_prepare_buffer(int right_eye)
{
    CitadelNativeWorldBuffer *buffer =
        &citadel_native_buffers[right_eye ? 1 : 0];

    if (!citadel_native_viewport_valid)
        return NULL;

    if (!buffer->valid) {
        buffer->count = 0;
        buffer->valid = 1;

        if (right_eye)
            ++citadel_native_stats.right_views;
        else
            ++citadel_native_stats.left_views;
    }

    return buffer;
}

static void citadel_native_note_range(float x, float y, float z)
{
    if (!citadel_native_stats.range_valid) {
        citadel_native_stats.minimum_x =
            citadel_native_stats.maximum_x = x;
        citadel_native_stats.minimum_y =
            citadel_native_stats.maximum_y = y;
        citadel_native_stats.minimum_z =
            citadel_native_stats.maximum_z = z;
        citadel_native_stats.range_valid = 1;
        return;
    }

    if (x < citadel_native_stats.minimum_x)
        citadel_native_stats.minimum_x = x;
    if (x > citadel_native_stats.maximum_x)
        citadel_native_stats.maximum_x = x;

    if (y < citadel_native_stats.minimum_y)
        citadel_native_stats.minimum_y = y;
    if (y > citadel_native_stats.maximum_y)
        citadel_native_stats.maximum_y = y;

    if (z < citadel_native_stats.minimum_z)
        citadel_native_stats.minimum_z = z;
    if (z > citadel_native_stats.maximum_z)
        citadel_native_stats.maximum_z = z;
}

static void citadel_native_fill_vertex(
    CitadelNativeWorldVertex *destination,
    g3s_phandle source,
    int light_flag)
{
    float light = 1.0f;

    destination->x = citadel_native_fix_to_float(source->gX);
    destination->y = citadel_native_fix_to_float(source->gY);
    destination->z = citadel_native_fix_to_float(source->gZ);

    /*
     * R3D4D: retain the exact post-clip software projection. Detail mode may
     * render into a smaller draw canvas, so convert local projected pixels to
     * the full placed gameplay viewport while view state is still live.
     */
    if (citadel_native_draw_width > 0 &&
        citadel_native_draw_height > 0 &&
        citadel_native_viewport_width > 0 &&
        citadel_native_viewport_height > 0 &&
        (source->p3_flags & PF_PROJECTED)) {
        destination->source_x =
            (float)citadel_native_viewport_x +
            ((float)source->sx / 65536.0f) *
            ((float)citadel_native_viewport_width /
             (float)citadel_native_draw_width);
        destination->source_y =
            (float)citadel_native_viewport_y +
            ((float)source->sy / 65536.0f) *
            ((float)citadel_native_viewport_height /
             (float)citadel_native_draw_height);
    } else {
        destination->source_x = 0.0f;
        destination->source_y = 0.0f;
    }

    destination->u = (float)source->uv.u / 256.0f;
    destination->v = (float)source->uv.v / 256.0f;

    if (light_flag && (source->p3_flags & PF_I))
        light = 1.0f - ((float)source->i / 4096.0f);

    destination->light = citadel_native_clamp_light(light);
}

static void citadel_native_append_triangle(
    g3s_phandle a,
    g3s_phandle b,
    g3s_phandle c,
    grs_bitmap *bitmap,
    uint64_t texture_content_key,
    uint8_t kind,
    int light_flag)
{
    CitadelNativeWorldBuffer *buffer;
    CitadelNativeWorldTriangle *triangle;

    float ax, ay, az;
    float bx, by, bz;
    float cx, cy, cz;

    float abx, aby, abz;
    float acx, acy, acz;
    float cross_x, cross_y, cross_z;
    float area_squared;

    if (a == NULL || b == NULL || c == NULL || bitmap == NULL)
        return;

    ax = citadel_native_fix_to_float(a->gX);
    ay = citadel_native_fix_to_float(a->gY);
    az = citadel_native_fix_to_float(a->gZ);

    bx = citadel_native_fix_to_float(b->gX);
    by = citadel_native_fix_to_float(b->gY);
    bz = citadel_native_fix_to_float(b->gZ);

    cx = citadel_native_fix_to_float(c->gX);
    cy = citadel_native_fix_to_float(c->gY);
    cz = citadel_native_fix_to_float(c->gZ);

    if (!isfinite(ax) || !isfinite(ay) || !isfinite(az) ||
        !isfinite(bx) || !isfinite(by) || !isfinite(bz) ||
        !isfinite(cx) || !isfinite(cy) || !isfinite(cz))
        return;

    if (az <= 0.001f || bz <= 0.001f || cz <= 0.001f) {
        ++citadel_native_stats.behind_or_near_rejects;
        return;
    }

    abx = bx - ax;
    aby = by - ay;
    abz = bz - az;

    acx = cx - ax;
    acy = cy - ay;
    acz = cz - az;

    cross_x = (aby * acz) - (abz * acy);
    cross_y = (abz * acx) - (abx * acz);
    cross_z = (abx * acy) - (aby * acx);

    area_squared =
        (cross_x * cross_x) +
        (cross_y * cross_y) +
        (cross_z * cross_z);

    if (area_squared < 0.00000001f) {
        ++citadel_native_stats.degenerate_rejects;
        return;
    }

    buffer = citadel_native_prepare_buffer(citadel_native_active_eye);

    if (buffer == NULL)
        return;

    if (buffer->count >= CITADEL_NATIVE_WORLD_MAX_TRIANGLES) {
        ++citadel_native_stats.capture_overflows;
        return;
    }

    triangle = &buffer->triangles[buffer->count++];

    citadel_native_fill_vertex(&triangle->vertices[0], a, light_flag);
    citadel_native_fill_vertex(&triangle->vertices[1], b, light_flag);
    citadel_native_fill_vertex(&triangle->vertices[2], c, light_flag);

    /* Preserve descriptor values before get_texture_map() mutates it. */
    triangle->bitmap = *bitmap;
    triangle->texture_content_key = texture_content_key;
    triangle->kind = kind;
    triangle->light_flag = light_flag ? 1u : 0u;
    triangle->bitmap_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
    triangle->reserved = 0;

    if (citadel_native_active_eye)
        ++citadel_native_stats.right_triangles_captured;
    else
        ++citadel_native_stats.left_triangles_captured;

    citadel_native_note_range(ax, ay, az);
    citadel_native_note_range(bx, by, bz);
    citadel_native_note_range(cx, cy, cz);

    if (kind == CITADEL_NATIVE_SURFACE_WALL)
        ++citadel_native_stats.wall_triangles_captured;
    else if (kind == CITADEL_NATIVE_SURFACE_FLOOR)
        ++citadel_native_stats.floor_triangles_captured;
    else if (kind == CITADEL_NATIVE_SURFACE_CEILING)
        ++citadel_native_stats.ceiling_triangles_captured;
    else if (kind == CITADEL_NATIVE_SURFACE_DOOR) {
        ++citadel_native_stats.door_triangles_captured;
        if (bitmap->flags & BMF_TRANS)
            ++citadel_native_stats.transparent_door_triangles_captured;
    } else if (kind == CITADEL_NATIVE_SURFACE_TEXBITMAP) {
        ++citadel_native_stats.texbitmap_triangles_captured;
    }
}

static void citadel_native_capture_fan(
    int n,
    g3s_phandle *points,
    grs_bitmap *bitmap,
    uint64_t texture_content_key,
    uint8_t kind,
    int light_flag)
{
    int index;

    if (n < 3 || points == NULL || bitmap == NULL)
        return;

    for (index = 1; index + 1 < n; ++index) {
        citadel_native_append_triangle(
            points[0],
            points[index],
            points[index + 1],
            bitmap,
            texture_content_key,
            kind,
            light_flag);
    }
}

static void citadel_native_fill_bitmap_vertex(
    CitadelNativeWorldVertex *destination,
    const grs_vertex *source,
    fix camera_z,
    float u,
    float v,
    fix light_value)
{
    float light = 1.0f;

    memset(destination, 0, sizeof(*destination));
    destination->z = citadel_native_fix_to_float(camera_z);

    if (citadel_native_draw_width > 0 &&
        citadel_native_draw_height > 0 &&
        citadel_native_viewport_width > 0 &&
        citadel_native_viewport_height > 0 &&
        source != NULL) {
        destination->source_x =
            (float)citadel_native_viewport_x +
            ((float)source->x / 65536.0f) *
            ((float)citadel_native_viewport_width /
             (float)citadel_native_draw_width);
        destination->source_y =
            (float)citadel_native_viewport_y +
            ((float)source->y / 65536.0f) *
            ((float)citadel_native_viewport_height /
             (float)citadel_native_draw_height);
    }

    destination->x = destination->source_x;
    destination->y = destination->source_y;
    destination->u = u;
    destination->v = v;

    light = 1.0f - ((float)(light_value & 0x0000FF00) / 4096.0f);
    destination->light = citadel_native_clamp_light(light);
}

static int citadel_native_append_bitmap_triangle(
    const grs_vertex *a,
    const grs_vertex *b,
    const grs_vertex *c,
    fix camera_z,
    grs_bitmap *bitmap,
    uint64_t texture_content_key,
    int corner_a,
    int corner_b,
    int corner_c,
    float u_max,
    float v_max,
    fix light_value)
{
    float uv[4][2];
    CitadelNativeWorldBuffer *buffer;
    CitadelNativeWorldTriangle *triangle;
    float ax;
    float ay;
    float bx;
    float by;
    float cx;
    float cy;
    float area;

    if (a == NULL || b == NULL || c == NULL || bitmap == NULL ||
        camera_z <= 0 ||
        u_max <= 0.0f || u_max > 1.0f ||
        v_max <= 0.0f || v_max > 1.0f)
        return 0;

    uv[0][0] = 0.0f;
    uv[0][1] = 0.0f;
    uv[1][0] = u_max;
    uv[1][1] = 0.0f;
    uv[2][0] = u_max;
    uv[2][1] = v_max;
    uv[3][0] = 0.0f;
    uv[3][1] = v_max;

    ax = (float)a->x / 65536.0f;
    ay = (float)a->y / 65536.0f;
    bx = (float)b->x / 65536.0f;
    by = (float)b->y / 65536.0f;
    cx = (float)c->x / 65536.0f;
    cy = (float)c->y / 65536.0f;
    area = ((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax));

    if (!isfinite(area) || fabsf(area) < 0.0001f) {
        ++citadel_native_stats.degenerate_rejects;
        return 0;
    }

    buffer = citadel_native_prepare_buffer(citadel_native_active_eye);
    if (buffer == NULL)
        return 0;

    if (buffer->count >= CITADEL_NATIVE_WORLD_MAX_TRIANGLES) {
        ++citadel_native_stats.capture_overflows;
        return 0;
    }

    triangle = &buffer->triangles[buffer->count++];
    citadel_native_fill_bitmap_vertex(
        &triangle->vertices[0], a, camera_z,
        uv[corner_a][0], uv[corner_a][1], light_value);
    citadel_native_fill_bitmap_vertex(
        &triangle->vertices[1], b, camera_z,
        uv[corner_b][0], uv[corner_b][1], light_value);
    citadel_native_fill_bitmap_vertex(
        &triangle->vertices[2], c, camera_z,
        uv[corner_c][0], uv[corner_c][1], light_value);

    triangle->bitmap = *bitmap;
    triangle->texture_content_key = texture_content_key;
    triangle->kind = CITADEL_NATIVE_SURFACE_WORLD_BITMAP;
    triangle->light_flag = 1u;
    triangle->bitmap_category =
        (uint8_t)citadel_native_bitmap_category;
    triangle->reserved = 0;

    if (citadel_native_active_eye)
        ++citadel_native_stats.right_triangles_captured;
    else
        ++citadel_native_stats.left_triangles_captured;

    citadel_native_note_range(ax, ay, citadel_native_fix_to_float(camera_z));
    citadel_native_note_range(bx, by, citadel_native_fix_to_float(camera_z));
    citadel_native_note_range(cx, cy, citadel_native_fix_to_float(camera_z));
    return 1;
}

void citadel_native_world_reset_all(void)
{
    memset(citadel_native_buffers, 0, sizeof(citadel_native_buffers));
    memset(&citadel_native_stats, 0, sizeof(citadel_native_stats));
    memset(
        citadel_native_door_texture_snapshots,
        0,
        sizeof(citadel_native_door_texture_snapshots));
    citadel_native_door_texture_snapshot_count = 0;
    citadel_native_last_door_snapshot = NULL;
    memset(
        citadel_native_texbitmap_texture_snapshots,
        0,
        sizeof(citadel_native_texbitmap_texture_snapshots));
    citadel_native_texbitmap_texture_snapshot_count = 0;
    citadel_native_last_texbitmap_snapshot = NULL;
    memset(
        citadel_native_bitmap_texture_snapshots,
        0,
        sizeof(citadel_native_bitmap_texture_snapshots));
    citadel_native_bitmap_texture_snapshot_count = 0;
    citadel_native_last_bitmap_snapshot = NULL;
    citadel_native_last_bitmap_capture_before_count = 0;
    citadel_native_last_bitmap_capture_count = 0;
    citadel_native_last_bitmap_capture_active = 0;
    citadel_native_bitmap_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
    citadel_native_last_bitmap_capture_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;

    citadel_native_surface_kind = CITADEL_NATIVE_SURFACE_NONE;
    citadel_native_active_eye = 0;
    citadel_native_engine_frame_open = 0;
    citadel_native_engine_frame_stereo = 0;
    citadel_native_engine_frame_split = 0;
    citadel_native_takeover_active = 0;
    citadel_native_takeover_present_active = 0;
    citadel_native_occlusion_saved_canvas = NULL;
    citadel_native_occlusion_reference_valid = 0;
    citadel_native_occlusion_draw_active = 0;
    citadel_native_viewport_valid = 0;
    citadel_native_viewport_x = 0;
    citadel_native_viewport_y = 0;
    citadel_native_viewport_width = 0;
    citadel_native_viewport_height = 0;
    citadel_native_draw_width = 0;
    citadel_native_draw_height = 0;
}

void citadel_native_world_begin_engine_frame(
    int stereo_enabled,
    int split_layout_enabled,
    int gameplay_active)
{
    citadel_native_buffers[0].valid = 0;
    citadel_native_buffers[1].valid = 0;
    citadel_native_door_texture_snapshot_count = 0;
    citadel_native_last_door_snapshot = NULL;
    citadel_native_texbitmap_texture_snapshot_count = 0;
    citadel_native_last_texbitmap_snapshot = NULL;
    citadel_native_bitmap_texture_snapshot_count = 0;
    citadel_native_last_bitmap_snapshot = NULL;
    citadel_native_last_bitmap_capture_before_count = 0;
    citadel_native_last_bitmap_capture_count = 0;
    citadel_native_last_bitmap_capture_active = 0;
    citadel_native_bitmap_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
    citadel_native_last_bitmap_capture_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;

    /*
     * R3D3C owns reference lifetime at the engine-frame boundary.
     * Clear any prior frame here, before the main view prepares a new
     * reference. Auxiliary views rendered after end_engine_frame() must not
     * invalidate the completed main-view reference before SDL presentation.
     */
    if (citadel_native_occlusion_draw_active)
        citadel_native_world_occlusion_reference_end_draw();
    citadel_native_occlusion_reference_valid = 0;
    citadel_native_occlusion_saved_canvas = NULL;
    citadel_native_occlusion_draw_active = 0;

    citadel_native_active_eye = 0;
    citadel_native_engine_frame_open = 1;
    citadel_native_engine_frame_stereo = stereo_enabled ? 1 : 0;
    citadel_native_engine_frame_split = split_layout_enabled ? 1 : 0;
    /*
     * R3D6A1: the exact R3D4D/R3D5 native capture path now owns ordinary
     * split-layout gameplay for BOTH eyes. render.c already executes an
     * explicit right pass followed by a left pass and selects the matching
     * native eye buffer before each fr_rend(). The software canvas therefore
     * becomes the keyed foreground layer in stereo exactly as it already is
     * in mono.
     */
    citadel_native_takeover_active =
        citadel_native_engine_frame_split &&
        gameplay_active;
    citadel_native_takeover_present_active =
        citadel_native_takeover_active;
    citadel_native_viewport_valid = 0;
    citadel_native_viewport_x = 0;
    citadel_native_viewport_y = 0;
    citadel_native_viewport_width = 0;
    citadel_native_viewport_height = 0;
    citadel_native_draw_width = 0;
    citadel_native_draw_height = 0;

    ++citadel_native_stats.engine_frames;

    if (citadel_native_engine_frame_stereo)
        ++citadel_native_stats.stereo_engine_frames;
    else
        ++citadel_native_stats.mono_engine_frames;

    if (citadel_native_engine_frame_split)
        ++citadel_native_stats.split_layout_engine_frames;

    if (citadel_native_engine_frame_split) {
        ++citadel_native_stats.takeover_eligible_frames;

        if (!gameplay_active)
            ++citadel_native_stats.paused_software_fallback_frames;
    }

    if (citadel_native_takeover_active)
        ++citadel_native_stats.takeover_active_frames;
}

void citadel_native_world_select_eye(int right_eye)
{
    citadel_native_active_eye = right_eye ? 1 : 0;

    if (citadel_native_active_eye)
        ++citadel_native_stats.right_eye_selects;
    else
        ++citadel_native_stats.left_eye_selects;
}

void citadel_native_world_end_engine_frame(void)
{
    citadel_native_engine_frame_open = 0;
    citadel_native_engine_frame_stereo = 0;
    citadel_native_engine_frame_split = 0;
    citadel_native_takeover_active = 0;
    citadel_native_occlusion_saved_canvas = NULL;
    citadel_native_occlusion_draw_active = 0;
    citadel_native_surface_kind = CITADEL_NATIVE_SURFACE_NONE;
}

int citadel_native_world_foreground_render_active(void)
{
    return citadel_native_takeover_active;
}

int citadel_native_world_foreground_present_active(void)
{
    return citadel_native_takeover_present_active;
}

int citadel_native_world_occlusion_reference_prepare(
    grs_canvas *source_canvas,
    int clear_color)
{
    size_t bytes;

    citadel_native_occlusion_reference_valid = 0;
    citadel_native_occlusion_saved_canvas = NULL;
    citadel_native_occlusion_draw_active = 0;

    if (!citadel_native_takeover_active ||
        source_canvas == NULL ||
        source_canvas->bm.bits == NULL ||
        source_canvas->bm.type != BMT_FLAT8 ||
        source_canvas->bm.w <= 0 ||
        source_canvas->bm.h <= 0) {
        citadel_native_takeover_present_active = 0;
        return 0;
    }

    if (citadel_native_occlusion_canvas == NULL ||
        citadel_native_occlusion_canvas->bm.w != source_canvas->bm.w ||
        citadel_native_occlusion_canvas->bm.h != source_canvas->bm.h) {
        if (citadel_native_occlusion_canvas != NULL)
            gr_free_canvas(citadel_native_occlusion_canvas);

        citadel_native_occlusion_canvas = gr_alloc_canvas(
            BMT_FLAT8,
            source_canvas->bm.w,
            source_canvas->bm.h);
    }

    if (citadel_native_occlusion_canvas == NULL ||
        citadel_native_occlusion_canvas->bm.bits == NULL) {
        ++citadel_native_stats.occlusion_reference_failures;
        citadel_native_takeover_present_active = 0;
        return 0;
    }

    citadel_native_occlusion_canvas->gc = source_canvas->gc;
    bytes = (size_t)citadel_native_occlusion_canvas->bm.row *
            (size_t)citadel_native_occlusion_canvas->bm.h;
    memset(citadel_native_occlusion_canvas->bm.bits,
           clear_color & 0xff,
           bytes);

    citadel_native_occlusion_reference_valid = 1;
    ++citadel_native_stats.occlusion_reference_frames;
    return 1;
}

int citadel_native_world_occlusion_reference_begin_draw(void)
{
    if (!citadel_native_takeover_active)
        return 0;

    if (!citadel_native_occlusion_reference_valid ||
        citadel_native_occlusion_canvas == NULL ||
        citadel_native_occlusion_draw_active) {
        ++citadel_native_stats.occlusion_reference_failures;
        citadel_native_takeover_present_active = 0;
        return 0;
    }

    citadel_native_occlusion_saved_canvas = grd_canvas;
    if (citadel_native_occlusion_saved_canvas == NULL) {
        ++citadel_native_stats.occlusion_reference_failures;
        citadel_native_takeover_present_active = 0;
        return 0;
    }

    citadel_native_occlusion_canvas->gc =
        citadel_native_occlusion_saved_canvas->gc;
    gr_set_canvas(citadel_native_occlusion_canvas);
    citadel_native_occlusion_draw_active = 1;
    ++citadel_native_stats.occlusion_reference_draws;
    return 1;
}

void citadel_native_world_occlusion_reference_end_draw(void)
{
    if (!citadel_native_occlusion_draw_active)
        return;

    gr_set_canvas(citadel_native_occlusion_saved_canvas);
    citadel_native_occlusion_saved_canvas = NULL;
    citadel_native_occlusion_draw_active = 0;
}

const grs_bitmap *citadel_native_world_occlusion_reference_bitmap(void)
{
    if (!citadel_native_occlusion_reference_valid ||
        citadel_native_occlusion_canvas == NULL) {
        return NULL;
    }

    return &citadel_native_occlusion_canvas->bm;
}

void citadel_native_world_occlusion_reference_invalidate(void)
{
    if (citadel_native_occlusion_draw_active)
        citadel_native_world_occlusion_reference_end_draw();

    citadel_native_occlusion_reference_valid = 0;
    citadel_native_takeover_present_active = 0;
}

void citadel_native_world_begin_view(
    int viewport_x,
    int viewport_y,
    int viewport_width,
    int viewport_height,
    int right_eye)
{
    CitadelNativeWorldBuffer *buffer;
    int requested_eye = right_eye ? 1 : 0;

    citadel_native_viewport_x = viewport_x;
    citadel_native_viewport_y = viewport_y;
    citadel_native_viewport_width = viewport_width;
    citadel_native_viewport_height = viewport_height;

    if (grd_canvas != NULL) {
        citadel_native_draw_width = grd_canvas->bm.w;
        citadel_native_draw_height = grd_canvas->bm.h;
    } else {
        citadel_native_draw_width = viewport_width;
        citadel_native_draw_height = viewport_height;
    }

    if (citadel_native_engine_frame_open &&
        requested_eye != citadel_native_active_eye) {
        ++citadel_native_stats.begin_view_eye_mismatches;
    }

    citadel_native_viewport_valid =
        viewport_width > 0 && viewport_height > 0;

    if (!citadel_native_viewport_valid)
        return;

    buffer = &citadel_native_buffers[citadel_native_active_eye];

    if (!buffer->valid) {
        buffer->count = 0;
        buffer->valid = 1;

        if (citadel_native_active_eye)
            ++citadel_native_stats.right_views;
        else
            ++citadel_native_stats.left_views;
    }
}

void citadel_native_world_set_surface_kind(int kind)
{
    switch (kind) {
    case CITADEL_NATIVE_SURFACE_WALL:
    case CITADEL_NATIVE_SURFACE_FLOOR:
    case CITADEL_NATIVE_SURFACE_CEILING:
    case CITADEL_NATIVE_SURFACE_DOOR:
    case CITADEL_NATIVE_SURFACE_WORLD_BITMAP:
    case CITADEL_NATIVE_SURFACE_TEXBITMAP:
        citadel_native_surface_kind = kind;
        break;

    default:
        citadel_native_surface_kind = CITADEL_NATIVE_SURFACE_NONE;
        break;
    }
}

void citadel_native_world_begin_bitmap_object_category(int category)
{
    switch (category) {
    case CITADEL_NATIVE_BITMAP_CATEGORY_STANDARD:
    case CITADEL_NATIVE_BITMAP_CATEGORY_CRITTER:
    case CITADEL_NATIVE_BITMAP_CATEGORY_MULTIVIEW:
        citadel_native_bitmap_category = category;
        break;

    default:
        citadel_native_bitmap_category =
            CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
        break;
    }

    citadel_native_surface_kind = CITADEL_NATIVE_SURFACE_WORLD_BITMAP;
    ++citadel_native_stats.bitmap_object_calls;

    if (citadel_native_bitmap_category_is_critter(
            citadel_native_bitmap_category)) {
        ++citadel_native_stats.critter_bitmap_calls;
    } else if (citadel_native_bitmap_category_is_multiview(
                   citadel_native_bitmap_category)) {
        ++citadel_native_stats.multiview_bitmap_calls;
    }
}

void citadel_native_world_begin_bitmap_object(void)
{
    citadel_native_world_begin_bitmap_object_category(
        CITADEL_NATIVE_BITMAP_CATEGORY_STANDARD);
}

void citadel_native_world_note_critter_special_software(void)
{
    ++citadel_native_stats.critter_special_software_exclusions;
}

void citadel_native_world_end_bitmap_object(void)
{
    if (citadel_native_surface_kind == CITADEL_NATIVE_SURFACE_WORLD_BITMAP)
        citadel_native_surface_kind = CITADEL_NATIVE_SURFACE_NONE;

    citadel_native_bitmap_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
}

int citadel_native_world_capture_bitmap(
    grs_bitmap *bitmap,
    grs_vertex **vertices,
    fix camera_z,
    fix light_value,
    int blending_enabled)
{
    CitadelNativeWorldBuffer *buffer;
    const CitadelNativeBitmapTextureSnapshot *snapshot;
    uint64_t content_key = 0;
    size_t before_count;
    size_t captured_count;

    if (citadel_native_surface_kind !=
        CITADEL_NATIVE_SURFACE_WORLD_BITMAP)
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;

    if (!citadel_native_takeover_active) {
        citadel_native_note_bitmap_category_fallback(
            citadel_native_bitmap_category,
            1);
        ++citadel_native_stats.bitmap_object_software_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    if (bitmap == NULL ||
        bitmap->type == BMT_TLUC8 ||
        (bitmap->flags & BMF_TLUC8) != 0) {
        if (citadel_native_bitmap_category_is_critter(
                citadel_native_bitmap_category)) {
            ++citadel_native_stats
                .critter_bitmap_true_blend_exclusions;
        } else if (citadel_native_bitmap_category_is_multiview(
                       citadel_native_bitmap_category)) {
            ++citadel_native_stats
                .multiview_bitmap_true_blend_exclusions;
        }
        citadel_native_note_bitmap_category_fallback(
            citadel_native_bitmap_category,
            1);
        ++citadel_native_stats.bitmap_object_blend_exclusions;
        ++citadel_native_stats.bitmap_object_software_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    /*
     * R3D5B1A: _g3d_enable_blend is the legacy large-bitmap
     * scale/filter optimization, not a translucent material class.
     * Actual translucent resources remain excluded above.
     */
    if (blending_enabled)
        ++citadel_native_stats.bitmap_object_legacy_blend_flags_accepted;

    if ((bitmap->flags & BMF_TRANS) == 0) {
        if (citadel_native_bitmap_category_is_critter(
                citadel_native_bitmap_category)) {
            ++citadel_native_stats
                .critter_bitmap_nonalpha_exclusions;
        } else if (citadel_native_bitmap_category_is_multiview(
                       citadel_native_bitmap_category)) {
            ++citadel_native_stats
                .multiview_bitmap_nonalpha_exclusions;
        }
        citadel_native_note_bitmap_category_fallback(
            citadel_native_bitmap_category,
            1);
        ++citadel_native_stats.bitmap_object_nonalpha_exclusions;
        ++citadel_native_stats.bitmap_object_software_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    /*
     * R3D5B1B: preserve the exact B1A eligibility behavior, but expose the
     * precise reason each standard bitmap remains on software fallback.
     */
    if (bitmap != NULL) {
        const uint32_t sample_width =
            bitmap->w > 0 ? (uint32_t)bitmap->w : 0u;
        const uint32_t sample_height =
            bitmap->h > 0 ? (uint32_t)bitmap->h : 0u;

        if (!citadel_native_stats.bitmap_object_first_sample_recorded) {
            citadel_native_stats.bitmap_object_first_sample_recorded = 1u;
            citadel_native_stats.bitmap_object_first_type = bitmap->type;
            citadel_native_stats.bitmap_object_first_flags = bitmap->flags;
            citadel_native_stats.bitmap_object_first_width = bitmap->w;
            citadel_native_stats.bitmap_object_first_height = bitmap->h;
            citadel_native_stats.bitmap_object_first_row = bitmap->row;
            citadel_native_stats.bitmap_object_first_camera_z = camera_z;
        }

        if (sample_width > 0u) {
            if (citadel_native_stats.bitmap_object_min_width == 0u ||
                sample_width <
                    citadel_native_stats.bitmap_object_min_width) {
                citadel_native_stats.bitmap_object_min_width = sample_width;
            }
            if (sample_width >
                citadel_native_stats.bitmap_object_max_width) {
                citadel_native_stats.bitmap_object_max_width = sample_width;
            }
        }

        if (sample_height > 0u) {
            if (citadel_native_stats.bitmap_object_min_height == 0u ||
                sample_height <
                    citadel_native_stats.bitmap_object_min_height) {
                citadel_native_stats.bitmap_object_min_height =
                    sample_height;
            }
            if (sample_height >
                citadel_native_stats.bitmap_object_max_height) {
                citadel_native_stats.bitmap_object_max_height =
                    sample_height;
            }
        }
    }

    if (vertices == NULL ||
        !citadel_native_bitmap_object_source_supported(bitmap) ||
        camera_z <= 0) {
        if (vertices == NULL)
            ++citadel_native_stats.bitmap_object_null_vertices_rejects;

        if (camera_z <= 0)
            ++citadel_native_stats.bitmap_object_camera_z_rejects;

        if (bitmap == NULL) {
            ++citadel_native_stats.bitmap_object_null_bitmap_rejects;
        } else {
            if (bitmap->bits == NULL)
                ++citadel_native_stats.bitmap_object_null_bits_rejects;

            if (bitmap->type != BMT_FLAT8 &&
                bitmap->type != BMT_RSD8) {
                ++citadel_native_stats.bitmap_object_type_rejects;
            }

            if (bitmap->w <= 0 || bitmap->h <= 0 ||
                bitmap->w >
                    (int)CITADEL_NATIVE_BITMAP_MAX_WIDTH ||
                bitmap->h >
                    (int)CITADEL_NATIVE_BITMAP_MAX_HEIGHT) {
                ++citadel_native_stats
                    .bitmap_object_dimension_range_rejects;
            }

            if (bitmap->type == BMT_FLAT8 &&
                bitmap->row < (ushort)bitmap->w) {
                ++citadel_native_stats.bitmap_object_row_pitch_rejects;
            }
        }

        citadel_native_note_bitmap_category_fallback(
            citadel_native_bitmap_category,
            0);
        ++citadel_native_stats.bitmap_object_capture_fallbacks;
        ++citadel_native_stats.bitmap_object_software_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    snapshot = citadel_native_snapshot_bitmap_object(
        bitmap,
        &content_key);
    if (snapshot == NULL) {
        citadel_native_note_bitmap_category_fallback(
            citadel_native_bitmap_category,
            0);
        ++citadel_native_stats.bitmap_object_capture_fallbacks;
        ++citadel_native_stats.bitmap_object_software_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    citadel_native_last_bitmap_snapshot = snapshot;
    citadel_native_last_bitmap_capture_active = 0;

    if (!citadel_native_is_power_of_two(
            (unsigned int)snapshot->source_width)) {
        ++citadel_native_stats.bitmap_object_npot_width_accepted;
    }
    if (!citadel_native_is_power_of_two(
            (unsigned int)snapshot->source_height)) {
        ++citadel_native_stats.bitmap_object_npot_height_accepted;
    }
    if (snapshot->source_width < 8)
        ++citadel_native_stats.bitmap_object_sub8_width_accepted;
    if (snapshot->source_height < 8)
        ++citadel_native_stats.bitmap_object_sub8_height_accepted;

    if (!citadel_native_stats.bitmap_object_first_texture_sample_recorded) {
        citadel_native_stats.bitmap_object_first_texture_sample_recorded = 1u;
        citadel_native_stats.bitmap_object_first_texture_width =
            snapshot->texture_width;
        citadel_native_stats.bitmap_object_first_texture_height =
            snapshot->texture_height;
        citadel_native_stats.bitmap_object_first_u_max =
            (float)snapshot->source_width /
            (float)snapshot->texture_width;
        citadel_native_stats.bitmap_object_first_v_max =
            (float)snapshot->source_height /
            (float)snapshot->texture_height;
    }

    buffer = &citadel_native_buffers[citadel_native_active_eye];
    before_count = buffer->valid ? buffer->count : 0;

    citadel_native_append_bitmap_triangle(
        vertices[0], vertices[1], vertices[2],
        camera_z, (grs_bitmap *)&snapshot->bitmap, content_key,
        0, 1, 2,
        (float)snapshot->source_width /
            (float)snapshot->texture_width,
        (float)snapshot->source_height /
            (float)snapshot->texture_height,
        light_value);
    citadel_native_append_bitmap_triangle(
        vertices[0], vertices[2], vertices[3],
        camera_z, (grs_bitmap *)&snapshot->bitmap, content_key,
        0, 2, 3,
        (float)snapshot->source_width /
            (float)snapshot->texture_width,
        (float)snapshot->source_height /
            (float)snapshot->texture_height,
        light_value);

    captured_count =
        (buffer->valid && buffer->count >= before_count)
            ? buffer->count - before_count
            : 0;

    if (captured_count != 2) {
        buffer->count = before_count;
        citadel_native_note_bitmap_category_fallback(
            citadel_native_bitmap_category,
            0);
        ++citadel_native_stats.bitmap_object_triangle_append_failures;
        ++citadel_native_stats.bitmap_object_capture_fallbacks;
        ++citadel_native_stats.bitmap_object_software_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    ++citadel_native_stats.bitmap_object_polygons_captured;
    citadel_native_stats.bitmap_object_triangles_captured += captured_count;
    ++citadel_native_stats.textured_polygons_captured;
    citadel_native_note_bitmap_category_capture(
        citadel_native_bitmap_category,
        captured_count);
    citadel_native_last_bitmap_capture_before_count = before_count;
    citadel_native_last_bitmap_capture_count = captured_count;
    citadel_native_last_bitmap_capture_active = 1;
    citadel_native_last_bitmap_capture_category =
        citadel_native_bitmap_category;
    return CITADEL_NATIVE_CAPTURE_BITMAP_ALPHA_ERASE;
}

int citadel_native_world_capture_tmap(
    int n,
    g3s_phandle *points,
    grs_bitmap *bitmap,
    int light_flag)
{
    CitadelNativeWorldBuffer *buffer;
    size_t before_count;
    size_t captured_count;
    const grs_bitmap *capture_bitmap = bitmap;
    uint64_t texture_content_key = 0;
    const int is_door =
        citadel_native_surface_kind == CITADEL_NATIVE_SURFACE_DOOR;
    const int is_texbitmap =
        citadel_native_surface_kind == CITADEL_NATIVE_SURFACE_TEXBITMAP;
    const int is_oriented_object = is_door || is_texbitmap;

    if (citadel_native_active_eye)
        ++citadel_native_stats.right_capture_calls;
    else
        ++citadel_native_stats.left_capture_calls;

    if (is_texbitmap)
        ++citadel_native_stats.texbitmap_calls;

    if (citadel_native_surface_kind == CITADEL_NATIVE_SURFACE_NONE) {
        ++citadel_native_stats.generic_textured_calls_skipped;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    /*
     * R3D6A1: doors and eligible oriented TEXBITMAP objects follow the same
     * per-eye native takeover policy as terrain. Pause/wrapper remain safe
     * software because citadel_native_takeover_active is false there.
     */
    if (is_oriented_object && !citadel_native_takeover_active)
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;

    if (!is_oriented_object &&
        bitmap != NULL &&
        (bitmap->flags & BMF_TRANS)) {
        ++citadel_native_stats.transparent_texture_fallbacks;
        if (citadel_native_takeover_active)
            ++citadel_native_stats.takeover_capture_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    if (!citadel_native_bitmap_supported(bitmap, is_oriented_object)) {
        ++citadel_native_stats.unsupported_texture_fallbacks;

        if (is_door) {
            ++citadel_native_stats.door_capture_fallbacks;
        } else if (is_texbitmap) {
            ++citadel_native_stats.texbitmap_capture_fallbacks;
            ++citadel_native_stats.texbitmap_software_fallbacks;
        } else if (citadel_native_takeover_active) {
            ++citadel_native_stats.takeover_capture_fallbacks;
        }

        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    if (is_door) {
        capture_bitmap = citadel_native_snapshot_door_bitmap(
            bitmap,
            &texture_content_key);

        if (capture_bitmap == NULL) {
            ++citadel_native_stats.door_capture_fallbacks;
            if (bitmap != NULL && (bitmap->flags & BMF_TRANS))
                ++citadel_native_stats.transparent_door_software_fallbacks;
            return CITADEL_NATIVE_CAPTURE_SOFTWARE;
        }

        citadel_native_last_door_snapshot = capture_bitmap;
    } else if (is_texbitmap) {
        capture_bitmap = citadel_native_snapshot_texbitmap(
            bitmap,
            &texture_content_key);

        if (capture_bitmap == NULL) {
            ++citadel_native_stats.texbitmap_capture_fallbacks;
            ++citadel_native_stats.texbitmap_software_fallbacks;
            return CITADEL_NATIVE_CAPTURE_SOFTWARE;
        }

        citadel_native_last_texbitmap_snapshot = capture_bitmap;
    }

    buffer = &citadel_native_buffers[citadel_native_active_eye];
    before_count = buffer->valid ? buffer->count : 0;

    citadel_native_capture_fan(
        n,
        points,
        (grs_bitmap *)capture_bitmap,
        texture_content_key,
        (uint8_t)citadel_native_surface_kind,
        light_flag);

    captured_count =
        (buffer->valid && buffer->count >= before_count)
            ? buffer->count - before_count
            : 0;

    if (captured_count > 0)
        ++citadel_native_stats.textured_polygons_captured;

    if (is_door) {
        if (captured_count == 0) {
            ++citadel_native_stats.door_capture_fallbacks;
            if (bitmap != NULL && (bitmap->flags & BMF_TRANS))
                ++citadel_native_stats.transparent_door_software_fallbacks;
            return CITADEL_NATIVE_CAPTURE_SOFTWARE;
        }

        ++citadel_native_stats.door_polygons_captured;

        if (bitmap != NULL && (bitmap->flags & BMF_TRANS)) {
            ++citadel_native_stats.transparent_door_polygons_captured;
            return CITADEL_NATIVE_CAPTURE_DOOR_ALPHA_ERASE;
        }

        ++citadel_native_stats.opaque_door_polygons_captured;
        ++citadel_native_stats.software_door_calls_suppressed;
        ++citadel_native_stats.software_door_key_erases;
        return CITADEL_NATIVE_CAPTURE_DOOR_ERASE;
    }

    if (is_texbitmap) {
        if (captured_count == 0) {
            ++citadel_native_stats.texbitmap_capture_fallbacks;
            ++citadel_native_stats.texbitmap_software_fallbacks;
            return CITADEL_NATIVE_CAPTURE_SOFTWARE;
        }

        ++citadel_native_stats.texbitmap_polygons_captured;

        if (bitmap != NULL && (bitmap->flags & BMF_TRANS)) {
            ++citadel_native_stats.texbitmap_alpha_polygons_captured;
            return CITADEL_NATIVE_CAPTURE_TEXBITMAP_ALPHA_ERASE;
        }

        ++citadel_native_stats.texbitmap_opaque_polygons_captured;
        ++citadel_native_stats.texbitmap_software_calls_suppressed;
        ++citadel_native_stats.texbitmap_key_erases;
        return CITADEL_NATIVE_CAPTURE_TEXBITMAP_ERASE;
    }

    if (!citadel_native_takeover_active)
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;

    if (captured_count == 0) {
        ++citadel_native_stats.takeover_capture_fallbacks;
        return CITADEL_NATIVE_CAPTURE_SOFTWARE;
    }

    ++citadel_native_stats.software_terrain_calls_retained;

    /*
     * R3D4A: return one requests a cheap key-zero polygon erase in the
     * software foreground canvas. The expensive textured CPU terrain mapper
     * is skipped while preserving original painter-order occlusion.
     */
    return CITADEL_NATIVE_CAPTURE_TERRAIN_ERASE;
}

void citadel_native_world_capture_poly(
    long color,
    int n,
    g3s_phandle *points,
    char gouraud_flag)
{
    (void)color;
    (void)n;
    (void)points;
    (void)gouraud_flag;

    ++citadel_native_stats.solid_polygon_calls_skipped;
}

const CitadelNativeWorldTriangle *citadel_native_world_get_triangles(
    int right_eye,
    size_t *count)
{
    CitadelNativeWorldBuffer *buffer =
        &citadel_native_buffers[right_eye ? 1 : 0];

    if (count != NULL)
        *count = buffer->valid ? buffer->count : 0;

    return buffer->triangles;
}

void citadel_native_world_note_draw(
    int right_eye,
    size_t triangles_drawn,
    size_t triangles_dropped)
{
    CitadelNativeWorldBuffer *buffer =
        &citadel_native_buffers[right_eye ? 1 : 0];

    if (right_eye) {
        citadel_native_stats.right_triangles_drawn += triangles_drawn;
        citadel_native_stats.right_last_count = (uint32_t)buffer->count;

        if (buffer->count > citadel_native_stats.right_peak_count)
            citadel_native_stats.right_peak_count = (uint32_t)buffer->count;
    } else {
        citadel_native_stats.left_triangles_drawn += triangles_drawn;
        citadel_native_stats.left_last_count = (uint32_t)buffer->count;

        if (buffer->count > citadel_native_stats.left_peak_count)
            citadel_native_stats.left_peak_count = (uint32_t)buffer->count;
    }

    citadel_native_stats.draw_budget_drops += triangles_dropped;
}

void citadel_native_world_finish_present(void)
{
    citadel_native_buffers[0].valid = 0;
    citadel_native_buffers[1].valid = 0;

    citadel_native_surface_kind = CITADEL_NATIVE_SURFACE_NONE;
    citadel_native_active_eye = 0;
    citadel_native_takeover_present_active = 0;
    citadel_native_occlusion_reference_valid = 0;
    citadel_native_viewport_valid = 0;
}

void citadel_native_world_get_stats(CitadelNativeWorldStats *stats)
{
    if (stats != NULL)
        *stats = citadel_native_stats;
}
