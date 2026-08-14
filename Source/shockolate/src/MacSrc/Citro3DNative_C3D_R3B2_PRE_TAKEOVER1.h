#ifndef CITADEL_CITRO3D_NATIVE_H
#define CITADEL_CITRO3D_NATIVE_H

#include <stddef.h>
#include <stdint.h>
#include "3d.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CITADEL_NATIVE_WORLD_MAX_TRIANGLES 4096u
#define CITADEL_NATIVE_WORLD_DRAW_BUDGET   1536u

enum {
    CITADEL_NATIVE_SURFACE_NONE = 0,
    CITADEL_NATIVE_SURFACE_WALL = 1,
    CITADEL_NATIVE_SURFACE_FLOOR = 2,
    CITADEL_NATIVE_SURFACE_CEILING = 3
};

typedef struct CitadelNativeWorldTriangle {
    float x0, y0, z0;
    float x1, y1, z1;
    float x2, y2, z2;
    uint8_t kind;
    uint8_t reserved[3];
} CitadelNativeWorldTriangle;

typedef struct CitadelNativeWorldStats {
    uint32_t left_views;
    uint32_t right_views;

    uint64_t engine_frames;
    uint64_t mono_engine_frames;
    uint64_t stereo_engine_frames;
    uint64_t left_eye_selects;
    uint64_t right_eye_selects;
    uint64_t begin_view_eye_mismatches;
    uint64_t left_capture_calls;
    uint64_t right_capture_calls;
    uint64_t left_triangles_captured;
    uint64_t right_triangles_captured;

    uint64_t wall_triangles_captured;
    uint64_t floor_triangles_captured;
    uint64_t ceiling_triangles_captured;

    uint64_t generic_textured_calls_skipped;
    uint64_t solid_polygon_calls_skipped;
    uint64_t behind_or_near_rejects;
    uint64_t degenerate_rejects;
    uint64_t capture_overflows;

    uint64_t left_triangles_drawn;
    uint64_t right_triangles_drawn;
    uint64_t draw_budget_drops;

    uint32_t left_last_count;
    uint32_t right_last_count;
    uint32_t left_peak_count;
    uint32_t right_peak_count;

    float minimum_x;
    float maximum_x;
    float minimum_y;
    float maximum_y;
    float minimum_z;
    float maximum_z;
    uint32_t range_valid;
} CitadelNativeWorldStats;

void citadel_native_world_reset_all(void);

void citadel_native_world_begin_engine_frame(int stereo_enabled);
void citadel_native_world_select_eye(int right_eye);
void citadel_native_world_end_engine_frame(void);

void citadel_native_world_begin_view(
    int viewport_x,
    int viewport_y,
    int viewport_width,
    int viewport_height,
    int right_eye);

void citadel_native_world_set_surface_kind(int kind);

void citadel_native_world_capture_tmap(
    int n,
    g3s_phandle *points,
    grs_bitmap *bitmap,
    int light_flag);

void citadel_native_world_capture_poly(
    long color,
    int n,
    g3s_phandle *points,
    char gouraud_flag);

const CitadelNativeWorldTriangle *citadel_native_world_get_triangles(
    int right_eye,
    size_t *count);

void citadel_native_world_note_draw(
    int right_eye,
    size_t triangles_drawn,
    size_t triangles_dropped);

void citadel_native_world_finish_present(void);
void citadel_native_world_get_stats(CitadelNativeWorldStats *stats);

#ifdef __cplusplus
}
#endif

#endif
