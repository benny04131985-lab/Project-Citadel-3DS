#!/usr/bin/env python3
from pathlib import Path
import re, sys
root=Path.cwd()
move_in=root/'src/GameSrc/movekeys.c'; look_in=root/'src/GameSrc/mouselook.c'
move_out=root/'src/GameSrc/movekeys_3DS_analog_V1.c'; look_out=root/'src/GameSrc/mouselook_3DS_native_V1.c'
def fail(m): print('ERROR:',m,file=sys.stderr); raise SystemExit(1)
if not move_in.is_file() or not look_in.is_file(): fail('Run from the Shockolate project root; src/GameSrc/movekeys.c and mouselook.c must exist.')
move=move_in.read_text(); look=look_in.read_text()
if 'PROJECT CITADEL MOVEKEYS V1' in move or 'PROJECT CITADEL MOUSELOOK V1' in look: fail('One source file already contains this patch.')
anchor='#define KEYBD_CONTROL_BANK 1'
if anchor not in move: fail('Could not find KEYBD_CONTROL_BANK in movekeys.c')
move=move.replace(anchor,anchor+'\n#if defined(__3DS__) || defined(_3DS)\n#warning "PROJECT CITADEL MOVEKEYS V1: direct Circle Pad physics are ACTIVE"\nextern void citadel_3ds_get_analog_movement(int *xvel, int *yvel);\n#endif',1)
pat=re.compile(r'void process_motion_keys\(void\)\s*\{\s*physics_set_player_controls\(\s*KEYBD_CONTROL_BANK,\s*poll_controls\[CONTROL_XVEL\],\s*poll_controls\[CONTROL_YVEL\],\s*poll_controls\[CONTROL_ZVEL\],\s*poll_controls\[CONTROL_XYROT\],\s*poll_controls\[CONTROL_YZROT\],\s*poll_controls\[CONTROL_XZROT\]\s*\);\s*\}',re.S)
rep='''void process_motion_keys(void) {\n    byte xvel=poll_controls[CONTROL_XVEL];\n    byte yvel=poll_controls[CONTROL_YVEL];\n#if defined(__3DS__) || defined(_3DS)\n    {\n        int ax=0,ay=0;\n        citadel_3ds_get_analog_movement(&ax,&ay);\n        if (abs(ax)>abs((int)xvel)) xvel=(byte)ax;\n        if (abs(ay)>abs((int)yvel)) yvel=(byte)ay;\n    }\n#endif\n    physics_set_player_controls(KEYBD_CONTROL_BANK,xvel,yvel,poll_controls[CONTROL_ZVEL],poll_controls[CONTROL_XYROT],poll_controls[CONTROL_YZROT],poll_controls[CONTROL_XZROT]);\n}'''
move,n=pat.subn(rep,move,1)
if n!=1: fail('Could not patch process_motion_keys()')
anchor='#include "Prefs.h"'
if anchor not in look: fail('Could not find Prefs.h in mouselook.c')
look=look.replace(anchor,anchor+'\n#if defined(__3DS__) || defined(_3DS)\n#warning "PROJECT CITADEL MOUSELOOK V1: native C-stick freelook is ACTIVE"\nextern int citadel_3ds_freelook_is_desired(void);\n#endif',1)
pat=re.compile(r'void mouse_look_physics\(\)\s*\{\s*if \(game_paused \|\| !global_fullmap \|\| !mlook_enabled\)\s*return;\s*middleize_mouse\(\);',re.S)
rep='''void mouse_look_physics() {\n#if defined(__3DS__) || defined(_3DS)\n    mlook_enabled = citadel_3ds_freelook_is_desired() ? TRUE : FALSE;\n#endif\n    if (game_paused || !global_fullmap || !mlook_enabled)\n        return;\n#if !defined(__3DS__) && !defined(_3DS)\n    middleize_mouse();\n#endif'''
look,n=pat.subn(rep,look,1)
if n!=1: fail('Could not patch mouse_look_physics()')
move_out.write_text(move); look_out.write_text(look)
print('Created:',move_out.relative_to(root)); print('Created:',look_out.relative_to(root)); print('Original files were left unchanged.')
