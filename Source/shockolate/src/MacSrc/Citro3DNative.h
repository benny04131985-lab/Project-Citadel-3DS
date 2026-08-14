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

#define CITADEL_NATIVE_CAPTURE_SOFTWARE       0
#define CITADEL_NATIVE_CAPTURE_TERRAIN_ERASE  1
#define CITADEL_NATIVE_CAPTURE_SUPPRESS       2
#define CITADEL_NATIVE_CAPTURE_DOOR_ERASE       3
#define CITADEL_NATIVE_CAPTURE_DOOR_ALPHA_ERASE 4
#define CITADEL_NATIVE_CAPTURE_BITMAP_ALPHA_ERASE 5
#define CITADEL_NATIVE_CAPTURE_TEXBITMAP_ERASE 6
#define CITADEL_NATIVE_CAPTURE_TEXBITMAP_ALPHA_ERASE 7

#define CITADEL_NATIVE_BITMAP_CATEGORY_NONE     0
#define CITADEL_NATIVE_BITMAP_CATEGORY_STANDARD  1
#define CITADEL_NATIVE_BITMAP_CATEGORY_CRITTER   2
#define CITADEL_NATIVE_BITMAP_CATEGORY_MULTIVIEW 3

enum {
    CITADEL_NATIVE_SURFACE_NONE = 0,
    CITADEL_NATIVE_SURFACE_WALL = 1,
    CITADEL_NATIVE_SURFACE_FLOOR = 2,
    CITADEL_NATIVE_SURFACE_CEILING = 3,
    CITADEL_NATIVE_SURFACE_DOOR = 4,
    CITADEL_NATIVE_SURFACE_WORLD_BITMAP = 5,
    CITADEL_NATIVE_SURFACE_TEXBITMAP = 6
};

typedef struct CitadelNativeWorldVertex {
    float x, y, z;
    float source_x, source_y;
    float u, v;
    float light;
} CitadelNativeWorldVertex;

typedef struct CitadelNativeWorldTriangle {
    CitadelNativeWorldVertex vertices[3];
    /* Snapshot: get_texture_map() reuses four mutable descriptors. */
    grs_bitmap bitmap;
    uint64_t texture_content_key;
    uint8_t kind;
    uint8_t light_flag;
    uint8_t bitmap_category;
    uint8_t reserved;
} CitadelNativeWorldTriangle;

typedef struct CitadelNativeWorldStats {
    uint32_t left_views;
    uint32_t right_views;

    uint64_t engine_frames;
    uint64_t mono_engine_frames;
    uint64_t stereo_engine_frames;
    uint64_t split_layout_engine_frames;
    uint64_t takeover_eligible_frames;
    uint64_t takeover_active_frames;
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
    uint64_t door_triangles_captured;
    uint64_t door_polygons_captured;
    uint64_t opaque_door_polygons_captured;
    uint64_t transparent_door_polygons_captured;
    uint64_t transparent_door_triangles_captured;
    uint64_t transparent_door_software_fallbacks;
    uint64_t transparent_door_mask_erases;
    uint64_t transparent_door_mask_failures;
    uint64_t transparent_door_mask_pixels_erased;
    uint64_t door_capture_fallbacks;
    uint64_t software_door_calls_suppressed;
    uint64_t software_door_key_erases;
    uint64_t door_texture_snapshots;
    uint64_t door_texture_snapshot_reuses;
    uint64_t door_texture_snapshot_failures;

    uint64_t texbitmap_calls;
    uint64_t texbitmap_polygons_captured;
    uint64_t texbitmap_triangles_captured;
    uint64_t texbitmap_opaque_polygons_captured;
    uint64_t texbitmap_alpha_polygons_captured;
    uint64_t texbitmap_software_calls_suppressed;
    uint64_t texbitmap_software_fallbacks;
    uint64_t texbitmap_capture_fallbacks;
    uint64_t texbitmap_key_erases;
    uint64_t texbitmap_mask_erases;
    uint64_t texbitmap_mask_failures;
    uint64_t texbitmap_mask_pixels_erased;
    uint64_t texbitmap_texture_snapshots;
    uint64_t texbitmap_texture_snapshot_reuses;
    uint64_t texbitmap_texture_snapshot_failures;

    uint64_t bitmap_object_calls;
    uint64_t bitmap_object_polygons_captured;
    uint64_t bitmap_object_triangles_captured;
    uint64_t bitmap_object_software_calls_suppressed;
    uint64_t bitmap_object_software_fallbacks;
    uint64_t bitmap_object_capture_fallbacks;
    uint64_t bitmap_object_texture_snapshots;
    uint64_t bitmap_object_texture_snapshot_reuses;
    uint64_t bitmap_object_texture_snapshot_failures;
    uint64_t bitmap_object_mask_erases;
    uint64_t bitmap_object_mask_failures;
    uint64_t bitmap_object_mask_pixels_erased;

    uint64_t bitmap_object_mask_state_failures;
    uint64_t bitmap_object_mask_canvas_failures;
    uint64_t bitmap_object_mask_source_failures;
    uint64_t bitmap_object_mask_offscreen_fallbacks;
    uint64_t bitmap_object_offscreen_exclusions;

    uint64_t bitmap_object_blend_exclusions;
    uint64_t bitmap_object_legacy_blend_flags_accepted;
    uint64_t bitmap_object_nonalpha_exclusions;

    uint64_t bitmap_object_null_vertices_rejects;
    uint64_t bitmap_object_null_bitmap_rejects;
    uint64_t bitmap_object_null_bits_rejects;
    uint64_t bitmap_object_type_rejects;
    uint64_t bitmap_object_dimension_range_rejects;
    uint64_t bitmap_object_npot_width_rejects;
    uint64_t bitmap_object_npot_height_rejects;
    uint64_t bitmap_object_row_pitch_rejects;
    uint64_t bitmap_object_camera_z_rejects;
    uint64_t bitmap_object_triangle_append_failures;

    uint64_t bitmap_object_npot_width_accepted;
    uint64_t bitmap_object_npot_height_accepted;
    uint64_t bitmap_object_sub8_width_accepted;
    uint64_t bitmap_object_sub8_height_accepted;
    uint64_t bitmap_object_padded_texture_snapshots;
    uint64_t bitmap_object_padding_texels;

    uint32_t bitmap_object_first_sample_recorded;
    int32_t bitmap_object_first_type;
    int32_t bitmap_object_first_flags;
    int32_t bitmap_object_first_width;
    int32_t bitmap_object_first_height;
    int32_t bitmap_object_first_row;
    int32_t bitmap_object_first_camera_z;

    uint32_t bitmap_object_min_width;
    uint32_t bitmap_object_max_width;
    uint32_t bitmap_object_min_height;
    uint32_t bitmap_object_max_height;

    uint32_t bitmap_object_first_texture_sample_recorded;
    int32_t bitmap_object_first_texture_width;
    int32_t bitmap_object_first_texture_height;
    float bitmap_object_first_u_max;
    float bitmap_object_first_v_max;

    uint64_t critter_bitmap_calls;
    uint64_t critter_bitmap_polygons_captured;
    uint64_t critter_bitmap_triangles_captured;
    uint64_t critter_bitmap_software_calls_suppressed;
    uint64_t critter_bitmap_expected_software_exclusions;
    uint64_t critter_bitmap_capture_failures;
    uint64_t critter_bitmap_mask_erases;
    uint64_t critter_bitmap_offscreen_exclusions;
    uint64_t critter_bitmap_true_blend_exclusions;
    uint64_t critter_bitmap_nonalpha_exclusions;
    uint64_t critter_special_software_exclusions;

    uint64_t multiview_bitmap_calls;
    uint64_t multiview_bitmap_polygons_captured;
    uint64_t multiview_bitmap_triangles_captured;
    uint64_t multiview_bitmap_software_calls_suppressed;
    uint64_t multiview_bitmap_expected_software_exclusions;
    uint64_t multiview_bitmap_capture_failures;
    uint64_t multiview_bitmap_mask_erases;
    uint64_t multiview_bitmap_offscreen_exclusions;
    uint64_t multiview_bitmap_true_blend_exclusions;
    uint64_t multiview_bitmap_nonalpha_exclusions;

    uint64_t textured_polygons_captured;
    uint64_t unsupported_texture_fallbacks;
    uint64_t transparent_texture_fallbacks;

    uint64_t generic_textured_calls_skipped;
    uint64_t solid_polygon_calls_skipped;
    uint64_t behind_or_near_rejects;
    uint64_t degenerate_rejects;
    uint64_t capture_overflows;
    uint64_t software_terrain_calls_suppressed;
    uint64_t left_software_terrain_calls_suppressed;
    uint64_t right_software_terrain_calls_suppressed;
    uint64_t takeover_capture_fallbacks;
    uint64_t software_terrain_calls_retained;
    uint64_t occlusion_reference_frames;
    uint64_t occlusion_reference_draws;
    uint64_t occlusion_reference_failures;
    uint64_t paused_software_fallback_frames;

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

void citadel_native_world_begin_engine_frame(
    int stereo_enabled,
    int split_layout_enabled,
    int gameplay_active);
void citadel_native_world_select_eye(int right_eye);
void citadel_native_world_end_engine_frame(void);

int citadel_native_world_foreground_render_active(void);
int citadel_native_world_foreground_present_active(void);

int citadel_native_world_occlusion_reference_prepare(
    grs_canvas *source_canvas,
    int clear_color);
int citadel_native_world_occlusion_reference_begin_draw(void);
void citadel_native_world_occlusion_reference_end_draw(void);
const grs_bitmap *citadel_native_world_occlusion_reference_bitmap(void);
void citadel_native_world_occlusion_reference_invalidate(void);

void citadel_native_world_begin_view(
    int viewport_x,
    int viewport_y,
    int viewport_width,
    int viewport_height,
    int right_eye);

void citadel_native_world_set_surface_kind(int kind);
void citadel_native_world_begin_bitmap_object(void);
void citadel_native_world_begin_bitmap_object_category(int category);
void citadel_native_world_note_critter_special_software(void);
void citadel_native_world_end_bitmap_object(void);

int citadel_native_world_capture_bitmap(
    grs_bitmap *bitmap,
    grs_vertex **vertices,
    fix camera_z,
    fix light_value,
    int blending_enabled);

int citadel_native_world_apply_transparent_bitmap_erase(
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info);
void citadel_native_world_cancel_bitmap_capture(void);

int citadel_native_world_apply_transparent_door_erase(
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info);

int citadel_native_world_apply_transparent_texbitmap_erase(
    int n,
    grs_vertex **vertices,
    grs_tmap_info *info);

int citadel_native_world_capture_tmap(
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
