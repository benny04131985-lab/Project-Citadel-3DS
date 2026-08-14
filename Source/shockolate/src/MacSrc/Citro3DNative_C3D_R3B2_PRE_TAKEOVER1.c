#include "Citro3DNative.h"

#include <math.h>
#include <string.h>

typedef struct CitadelNativeWorldBuffer {
    CitadelNativeWorldTriangle triangles[
        CITADEL_NATIVE_WORLD_MAX_TRIANGLES];
    size_t count;
    int valid;
} CitadelNativeWorldBuffer;

static CitadelNativeWorldBuffer citadel_native_buffers[2];
static CitadelNativeWorldStats citadel_native_stats;

static int citadel_native_surface_kind =
    CITADEL_NATIVE_SURFACE_NONE;

static int citadel_native_active_eye = 0;
static int citadel_native_engine_frame_open = 0;
static int citadel_native_engine_frame_stereo = 0;

static int citadel_native_viewport_valid;

static float citadel_native_fix_to_float(fix value)
{
    return (float)value / 65536.0f;
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

static void citadel_native_append_triangle(
    g3s_phandle a,
    g3s_phandle b,
    g3s_phandle c,
    uint8_t kind)
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

    if (a == NULL || b == NULL || c == NULL)
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

    /*
     * Shock's clipper keeps real world polygons in front of the camera.
     * Reject anything touching/behind the camera before PICA receives it.
     */
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

    buffer = citadel_native_prepare_buffer(
        citadel_native_active_eye);

    if (buffer == NULL)
        return;

    if (buffer->count >= CITADEL_NATIVE_WORLD_MAX_TRIANGLES) {
        ++citadel_native_stats.capture_overflows;
        return;
    }

    triangle = &buffer->triangles[buffer->count++];

    triangle->x0 = ax;
    triangle->y0 = ay;
    triangle->z0 = az;

    triangle->x1 = bx;
    triangle->y1 = by;
    triangle->z1 = bz;

    triangle->x2 = cx;
    triangle->y2 = cy;
    triangle->z2 = cz;

    triangle->kind = kind;
    triangle->reserved[0] = 0;
    triangle->reserved[1] = 0;
    triangle->reserved[2] = 0;

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
}

static void citadel_native_capture_fan(
    int n,
    g3s_phandle *points,
    uint8_t kind)
{
    int index;

    if (n < 3 || points == NULL)
        return;

    for (index = 1; index + 1 < n; ++index) {
        citadel_native_append_triangle(
            points[0],
            points[index],
            points[index + 1],
            kind);
    }
}

void citadel_native_world_reset_all(void)
{
    memset(citadel_native_buffers, 0, sizeof(citadel_native_buffers));
    memset(&citadel_native_stats, 0, sizeof(citadel_native_stats));

    citadel_native_surface_kind =
        CITADEL_NATIVE_SURFACE_NONE;
    citadel_native_active_eye = 0;
    citadel_native_engine_frame_open = 0;
    citadel_native_engine_frame_stereo = 0;
    citadel_native_viewport_valid = 0;
}

void citadel_native_world_begin_engine_frame(int stereo_enabled)
{
    citadel_native_buffers[0].valid = 0;
    citadel_native_buffers[1].valid = 0;

    citadel_native_active_eye = 0;
    citadel_native_engine_frame_open = 1;
    citadel_native_engine_frame_stereo = stereo_enabled ? 1 : 0;
    citadel_native_viewport_valid = 0;

    ++citadel_native_stats.engine_frames;

    if (citadel_native_engine_frame_stereo)
        ++citadel_native_stats.stereo_engine_frames;
    else
        ++citadel_native_stats.mono_engine_frames;
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
    citadel_native_surface_kind =
        CITADEL_NATIVE_SURFACE_NONE;
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

    (void)viewport_x;
    (void)viewport_y;

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
        citadel_native_surface_kind = kind;
        break;

    default:
        citadel_native_surface_kind =
            CITADEL_NATIVE_SURFACE_NONE;
        break;
    }
}

void citadel_native_world_capture_tmap(
    int n,
    g3s_phandle *points,
    grs_bitmap *bitmap,
    int light_flag)
{
    (void)bitmap;
    (void)light_flag;

    if (citadel_native_active_eye)
        ++citadel_native_stats.right_capture_calls;
    else
        ++citadel_native_stats.left_capture_calls;

    if (citadel_native_surface_kind ==
        CITADEL_NATIVE_SURFACE_NONE) {
        ++citadel_native_stats.generic_textured_calls_skipped;
        return;
    }

    citadel_native_capture_fan(
        n,
        points,
        (uint8_t)citadel_native_surface_kind);
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

    /* Exclude solid/fog/force-field/HUD polygons from R3A2. */
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
        citadel_native_stats.right_triangles_drawn +=
            triangles_drawn;
        citadel_native_stats.right_last_count =
            (uint32_t)buffer->count;

        if (buffer->count >
            citadel_native_stats.right_peak_count) {
            citadel_native_stats.right_peak_count =
                (uint32_t)buffer->count;
        }
    } else {
        citadel_native_stats.left_triangles_drawn +=
            triangles_drawn;
        citadel_native_stats.left_last_count =
            (uint32_t)buffer->count;

        if (buffer->count >
            citadel_native_stats.left_peak_count) {
            citadel_native_stats.left_peak_count =
                (uint32_t)buffer->count;
        }
    }

    citadel_native_stats.draw_budget_drops +=
        triangles_dropped;
}

void citadel_native_world_finish_present(void)
{
    citadel_native_buffers[0].valid = 0;
    citadel_native_buffers[1].valid = 0;

    citadel_native_surface_kind =
        CITADEL_NATIVE_SURFACE_NONE;
    citadel_native_active_eye = 0;
    citadel_native_viewport_valid = 0;
}

void citadel_native_world_get_stats(CitadelNativeWorldStats *stats)
{
    if (stats != NULL)
        *stats = citadel_native_stats;
}
