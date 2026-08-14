#!/usr/bin/env python3
from __future__ import annotations
import base64, datetime as dt, hashlib, json, os, re, shutil, sys
from pathlib import Path

P=Path("/c/Projects")
DEV=P/"Citadel_Citro3D_R3D7_AVP_STEREO_DEV"
SRC=DEV/"Source/shockolate"
SDL=DEV/"Libraries/SDL2"
BIN=P/"CITADEL_C3D_R3D7C_CMDBUF512_SHIPRC1.3dsx"
REPORT=P/"CITADEL_C3D_R3D7C_CMDBUF512_SHIPRC1_STAGE_REPORT.txt"

SHIP=P/"CITADEL_3DS_V2.0.0_SHIPPED"
READ=SHIP/"00_READ_ME_FIRST"
OURS=SHIP/"01_FOR_US_MASTER"
GH=SHIP/"02_GITHUB_DISTRIBUTION"
EVD=SHIP/"03_FINAL_EVIDENCE"
MAN=SHIP/"04_MANIFESTS"

VER="v2.0.0"
MILESTONE="CITADEL-C3D-R3D7C-CMDBUF512-SHIPRC1"
TOKEN="1786136661_000000A90E3ACF6E"

SHOCK="d1b66c2819124512065a66d4fa4d185a768249b514dbfe4a992f4e8a19b60e85"
FRSETUP="061255e8810ebcd54d4c05018c9621a31c96ae6f0070f8bc90a3074029315d67"
COMP={
"src/MacSrc/Citro3DNative.c":"43444641a52eedb2e439a345e11ca18113a9433996e9624b6792c2dfa3bb76f5",
"src/MacSrc/Citro3DNative.h":"abae30b1bd34f645ba696be5a491cd7a7a979d711ec1552aecbcf2e16084d9b1",
"src/GameSrc/gameobj.c":"440772d3512f825980c7c5f659cdbcff421f0d52bb0e44d705a0932cd41ce119",
"src/Libraries/3D/Source/tmap.c":"25f6b0adafd8b0aa0b7406a8a806ae91193229763efd38f730a2adc22d5f53a1",
"src/Libraries/3D/Source/Bitmap.c":"b26bb99af4f41c031543fa30a2458b77280c532c5a400291968f44f7f039943c",
"src/GameSrc/frterr.c":"f256fba4ea510e2671b3945a3ffef4ec81bf6a2f249dceea80a3d9111016ac2d",
"src/MacSrc/citadel_worldproof_vshader.v.pica":"b7df12598762ea1605ec09ad9230da27af311f25c328372d41783380090f742a",
"src/MacSrc/citadel_worldtextured_vshader.v.pica":"4ea3978bd25e70ffaa73e4fc856d0682edd7cd8647f4013b8e78e55deb407b3b",
}
EVIDENCE={'C3D_RUN_R3D7C_1786136661_000000A90E3ACF6E_STARTED.txt': 'UFJPSkVDVCBDSVRBREVMIFVOSVFVRSBSVU4gRVZJREVOQ0UKTG9nZ2VyIG1pbGVzdG9uZTogQ0lUQURFTC1DM0QtUjNEN0MtQ01EQlVGNTEyLVNISVBSQzEKUmVuZGVyZXIgbWlsZXN0b25lOiBDSVRBREVMLUMzRC1SM0Q3Qy1DTURCVUY1MTItU0hJUFJDMQpCdWlsZDogQXVnICA4IDIwMjYgMjA6MzY6NDcKUnVuIHRva2VuOiAxNzg2MTM2NjYxXzAwMDAwMEE5MEUzQUNGNkUKU2Vzc2lvbiBlcG9jaDogMTc4NjEzNjY2MQpIYXJkd2FyZSB0aWNrOiAweDAwMDAwMEE5MEUzQUNGNkUKRXhwZWN0ZWQgcHJvb2YgbG9nOiBzZG1jOi8zZHMvU3lzdGVtU2hvY2szRC9DM0RfUlVOX1IzRDdDXzE3ODYxMzY2NjFfMDAwMDAwQTkwRTNBQ0Y2RV9ERVBUSF9QUk9PRi5sb2cKRXhwZWN0ZWQgZGlhZyBsb2c6IHNkbWM6LzNkcy9TeXN0ZW1TaG9jazNEL0MzRF9SVU5fUjNEN0NfMTc4NjEzNjY2MV8wMDAwMDBBOTBFM0FDRjZFX0RJQUcubG9nCg==', 'C3D_RUN_R3D7C_1786136661_000000A90E3ACF6E_DEPTH_PROOF.log': 'PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09ClBST0pFQ1QgQ0lUQURFTCBDM0QgUjNEN0MgQ01EQlVGNTEyIFNISVBSQzEgQUNUSVZFCj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQpNaWxlc3RvbmU6IENJVEFERUwtQzNELVIzRDdDLUNNREJVRjUxMi1TSElQUkMxClJ1biB0b2tlbjogMTc4NjEzNjY2MV8wMDAwMDBBOTBFM0FDRjZFCk91dHB1dCBwYXRoOiBzZG1jOi8zZHMvU3lzdGVtU2hvY2szRC9DM0RfUlVOX1IzRDdDXzE3ODYxMzY2NjFfMDAwMDAwQTkwRTNBQ0Y2RV9ERVBUSF9QUk9PRi5sb2cKQnVpbGQ6IEF1ZyAgOCAyMDI2IDIwOjM2OjQ3ClBhcmVudCByZW5kZXJlcjogQ0lUQURFTC1DM0QtUjNEN0ItQVZQLURFUFRILVdBUlAxLUhXUEFTUwpBcmNoaXRlY3R1cmU6IEFWUF9TVFlMRV9TSU5HTEVfU1RSRUFNX0lNTUVESUFURV9EVUFMX1RBUkdFVApTdGVyZW8gc2NlbmUgdHJhdmVyc2FsOiBPTkVfRlJfUkVORF9PTkxZCk5hdGl2ZSBjYXB0dXJlIHBvbGljeTogTEVGVF9DQVBUVVJFX1JFVVNFRF9GT1JfUEhZU0lDQUxfUklHSFQKUjNEN0IgZGlzcGFyaXR5IHBvbGljeTogUklHSFRfT05MWV9SRUNJUFJPQ0FMX1dfREVQVEhfV0FSUApXYXJwIGZvcm11bGE6IHNoaWZ0X3B4PS1zdHJlbmd0aCooMS9tYXgoVywwLjI1KS0xLzIuMCkKRnVsbC1zbGlkZXIgcmVjaXByb2NhbCBzY2FsZTogMi4yMDAgcHgKTWF4aW11bSBhYnNvbHV0ZSB3YXJwOiA4LjAwMCBweApDaXRybzNEIGNvbW1hbmQgYnVmZmVyOiA1MjQyODggYnl0ZXMgKDUxMiBLaUIpCkNvbW1hbmQtYnVmZmVyIHRlbGVtZXRyeTogRU5BQkxFRF9QRVJfQ09NUExFVEVEX0ZSQU1FClJlbGVhc2Ugcm9sZTogVjIuMC4wX1NISVBfQ0FORElEQVRFX0hBUkRFTklORwpQaHlzaWNhbCByaWdodCB0YXJnZXQ6IFNBTUVfTkFUSVZFX1NUUkVBTV9BU19MRUZUX1dJVEhfREVQVEhfV0FSUApSaWdodCBzb2Z0d2FyZSByZXNpZHVhbDogRElTQUJMRUQKUmlnaHQgZnJhbWVidWZmZXIgcmVjb25zdHJ1Y3Rpb246IERJU0FCTEVECkxlZnQgc29mdHdhcmUgYmFzZWxpbmUgY2FwdHVyZTogRElTQUJMRUQKRmxhdCBmb3JlZ3JvdW5kIHBvbGljeTogT05FX0xFRlRfVEVYVFVSRV9SRVVTRURfQk9USF9FWUVTX1pFUk9fRElTUEFSSVRZCkhVRC9vdmVybGF5IGNhbGxiYWNrIGNvdW50OiBPTkVfTEVGVF9QQVNTX09OTFkKQm90dG9tLXNjcmVlbiBzb2Z0d2FyZSB0cmFuc3BvcnQ6IFBSRVNFUlZFRApOZXh0IGFmdGVyIHByb29mOiBWMi4wLjBfU0hJUF9JRl9NT05PX1NURVJFT19BTkRfSEVBRFJPT01fUEFTUwpTaHV0ZG93biBzdW1tYXJ5IHBlbmRpbmc6IFlFUwo9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCj09PT09PT09PT09PT09PT09PT09IFNFU1NJT04gU1VNTUFSWSA9PT09PT09PT09PT09PT09PT09PT09PQpNaWxlc3RvbmU6IENJVEFERUwtQzNELVIzRDdDLUNNREJVRjUxMi1TSElQUkMxClJ1biB0b2tlbjogMTc4NjEzNjY2MV8wMDAwMDBBOTBFM0FDRjZFClIzRDdDIHNoaXAtY2FuZGlkYXRlIHJlbmRlcmVyIHBhdGggcHJvdmVuOiBZRVMKU3RlcmVvIGZyYW1lcyBzY2hlZHVsZWQ6IDMwNjAKU2hvY2svZnJfcmVuZCBzY2VuZSB0cmF2ZXJzYWxzOiAzMDYwClBoeXNpY2FsIHJpZ2h0IGVuZ2luZSB0cmF2ZXJzYWxzIHNraXBwZWQ6IDMwNjAKUjNEN0EgYmFzZSBsZWZ0IHBhcml0eSBwYXNzZXM6IDMwNjAKTGVmdCBzb2Z0d2FyZSBiYXNlbGluZSBjYXB0dXJlcyBieXBhc3NlZDogMzA2MApMZWdhY3kgcmlnaHQgY29tcG9zaXRvciBwYXNzZXMgYnlwYXNzZWQ6IDMwNjAKVW5leHBlY3RlZCBvbGQgcmlnaHQgZW5naW5lIHBhc3NlczogMApSaWdodCBzb2Z0d2FyZSBmcmFtZSBhY3RpdmF0aW9uczogMApOYXRpdmUgTEVGVCB0cmlhbmdsZXMgY2FwdHVyZWQ6IDI1ODA4NQpOYXRpdmUgUklHSFQgdHJpYW5nbGVzIGNhcHR1cmVkOiAwClBoeXNpY2FsLXJpZ2h0IG5hdGl2ZSBkcmF3IGNhbGxzOiAzMDUzClBoeXNpY2FsLXJpZ2h0IG5hdGl2ZSB0cmlhbmdsZXM6IDE3MjEwOApSM0Q3QiByaWdodCBkZXB0aC13YXJwIGRyYXdzOiAzMDUzClIzRDdCIHJpZ2h0IGRlcHRoLXdhcnAgdmVydGljZXM6IDUxNjMyNApSM0Q3QiB6ZXJvLXNsaWRlciByaWdodCBkcmF3czogMApSM0Q3QiBtYXhpbXVtIHNsaWRlciBzZWVuOiAxLjAwMDAKUjNEN0Igc291cmNlIFcgcmFuZ2U6IDAuMDA2MTM0IC4uIDYuMjkzMjEzClIzRDdCIHJpZ2h0IHNoaWZ0IHJhbmdlIHBpeGVsczogLTcuNzAwMDAwIC4uIDAuNzUwNDE3ClIzRDdCIG5lYXIgY2xhbXAgVzogMC4yNTAKUjNEN0IgY29udmVyZ2VuY2UgVzogMi4wMDAKUjNEN0IgZnVsbC1zbGlkZXIgcmVjaXByb2NhbCBzY2FsZTogMi4yMDAKUjNEN0IgbWF4aW11bSBhYnNvbHV0ZSBzaGlmdDogOC4wMDAKTGVmdCBmb3JlZ3JvdW5kIGZyYW1lcyBidWlsdDogNTI1MgpTZXBhcmF0ZSByaWdodCBmb3JlZ3JvdW5kIGZyYW1lcyBidWlsdDogMApMZWZ0IGZvcmVncm91bmQgZHJhd3M6IDUyNTIKUGh5c2ljYWwtcmlnaHQgRkxBVCBmb3JlZ3JvdW5kIGRyYXdzOiAzMDU5CkZvcmVncm91bmQgYnVpbGQgZmFpbHVyZXM6IDAKRm9yZWdyb3VuZCByaWdodC1leWUgYnVpbGQgZmFpbHVyZXM6IDAKRm9yZWdyb3VuZCBkcmF3IGZhaWx1cmVzOiAwCkNhcHR1cmUgb3ZlcmZsb3dzOiAwCkRyYXctYnVkZ2V0IGRyb3BzOiAwCkdQVSB0ZXh0dXJlIHVwbG9hZCBmYWlsdXJlczogMApHUFUgcHJlc2VudGF0aW9uIHVwbG9hZCBmYWlsdXJlczogMApHUFUgZHJhdyBmYWlsdXJlczogMApDaXRybzNEIGNvbW1hbmQgYnVmZmVyIHNpemU6IDUyNDI4OCBieXRlcwpDb21tYW5kLWJ1ZmZlciB1c2FnZSBzYW1wbGVzOiA3MDI1CkNvbW1hbmQtYnVmZmVyIHBlYWsgdXNhZ2U6IDMwLjU4OCAlCkNvbW1hbmQtYnVmZmVyIHBlYWsgZXN0aW1hdGVkIGJ5dGVzOiAxNjAzNjgKTW9ubyBtZWFzdXJlZCBmcmFtZXM6IDM4MzcKTW9ubyBhdmVyYWdlIEZQUzogMzAuODMyClN0ZXJlbyBtZWFzdXJlZCBmcmFtZXM6IDMxODIKU3RlcmVvIGF2ZXJhZ2UgRlBTOiAyMy44MzYKUjNEN0MgdmlzdWFsIGNvbnRyYWN0OiBSM0Q3Ql9ERVBUSF9IVURfRkxBVF9QTFVTX0NNREJVRl9IRUFEUk9PTQpDbGVhbiBTaHV0ZG93bjogWUVTCj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQo=', 'C3D_RUN_R3D7C_1786136661_000000A90E3ACF6E_DIAG.log': 'PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CkNJVEFERUwgM0RTIFNJTEVOVCBESUFHTk9TVElDIExPRwo9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KVmVyc2lvbjogMS4wLjMtRElBRzQtVU5JUVVFLVJVTgpSdW4gdG9rZW46IDE3ODYxMzY2NjFfMDAwMDAwQTkwRTNBQ0Y2RQpSZW5kZXJlciBtaWxlc3RvbmU6IENJVEFERUwtQzNELVIzRDdDLUNNREJVRjUxMi1TSElQUkMxCkJ1aWxkOiBBdWcgIDggMjAyNiAyMDozNjo0NwpPdXRwdXQgcGF0aDogc2RtYzovM2RzL1N5c3RlbVNob2NrM0QvQzNEX1JVTl9SM0Q3Q18xNzg2MTM2NjYxXzAwMDAwMEE5MEUzQUNGNkVfRElBRy5sb2cKUHJpbWFyeSByZW1vdmUgcmVzdWx0OiAtMSBlcnJubz0yClByaW1hcnkgb3BlbjogWUVTIGVycm5vPTAKRmFsbGJhY2sgb3BlbjogTk8gZXJybm89MApTZXNzaW9uIHN0YXJ0IGVwb2NoOiAxNzg2MTM2NjYxCkhhcmR3YXJlIGRldGVjdGVkOiBOZXcgTmludGVuZG8gM0RTCk5ldyAzRFMgc3BlZWR1cCByZXF1ZXN0ZWQ6IFlFUwpTcGVlZHVwIHN0YXRlIGluZGVwZW5kZW50bHkgdmVyaWZpZWQ6IE5PCkluaXRpYWwgM0Qgc2xpZGVyOiAwLjAwMApJbml0aWFsIGxpbmVhciBtZW1vcnkgZnJlZTogMzE0MDQwMzIgYnl0ZXMKQ2l0cm8zRCBjb21tYW5kIGJ1ZmZlcjogNTI0Mjg4IGJ5dGVzICg1MTIgS2lCIHNoaXAgaGVhZHJvb20pCkNvbW1hbmQtYnVmZmVyIHVzYWdlIHRlbGVtZXRyeTogQzNEX0dldENtZEJ1ZlVzYWdlIEVBQ0ggQ09NUExFVEVEIEZSQU1FClRpbWVyIGZyZXF1ZW5jeTogMjY4MTExODU2IHRpY2tzL3NlYwpGcmFtZSB0aW1pbmcgc291cmNlOiBjb21wbGV0ZWQgQ2l0cm8zRCBwcmVzZW50YXRpb25zCkxvbmcgZ2FwcyBleGNsdWRlZCBmcm9tIEZQUyBhdmVyYWdlOiA+IDEwMDAgbXMKQ2xlYW4gU2h1dGRvd246IE5PCj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQoKPT09PT09PT09PT09PT09PT09PT0gU0VTU0lPTiBTVU1NQVJZID09PT09PT09PT09PT09PT09PT09PT09ClNlc3Npb24gZW5kIGVwb2NoOiAxNzg2MTM2OTcxClNlc3Npb24gZHVyYXRpb246IDMxMC4xNjkgc2Vjb25kcwpNZWFzdXJlZCBmcmFtZXM6IDcwMTkKTW9uby1zbGlkZXIgZnJhbWVzOiAzODM3Ck1vbm8gYXZlcmFnZSBGUFM6IDMwLjgzMgpNb25vIGF2ZXJhZ2UgZnJhbWUgdGltZTogMzIuNDMzIG1zCk1vbm8gYmVzdCBmcmFtZSB0aW1lOiAxNS45MTkgbXMKTW9ubyB3b3JzdCBmcmFtZSB0aW1lOiA0MDEuNjk3IG1zClN0ZXJlby1zbGlkZXIgZnJhbWVzOiAzMTgyClN0ZXJlbyBhdmVyYWdlIEZQUzogMjMuODM2ClN0ZXJlbyBhdmVyYWdlIGZyYW1lIHRpbWU6IDQxLjk1NCBtcwpTdGVyZW8gYmVzdCBmcmFtZSB0aW1lOiAxNi4xMDMgbXMKU3RlcmVvIHdvcnN0IGZyYW1lIHRpbWU6IDU1OS45NzYgbXMKQ29tYmluZWQgYXZlcmFnZSBGUFM6IDI3LjIxMQpBdmVyYWdlIGZyYW1lIHRpbWU6IDM2Ljc0OSBtcwpCZXN0IGZyYW1lIHRpbWU6IDE1LjkxOSBtcwpNZWRpYW4gZnJhbWUgdGltZSAoMSBtcyBoaXN0b2dyYW0pOiAzMyBtcwpQOTUgZnJhbWUgdGltZSAoMSBtcyBoaXN0b2dyYW0pOiA2NiBtcwpQOTkgZnJhbWUgdGltZSAoMSBtcyBoaXN0b2dyYW0pOiA4NCBtcwpXb3JzdCBtZWFzdXJlZCBmcmFtZTogNTU5Ljk3NiBtcwpGcmFtZXMgb3ZlciAxNi42NyBtczogNjM2MwpGcmFtZXMgb3ZlciAzMy4zMyBtczogNDI4OQpGcmFtZXMgb3ZlciA1MCBtczogMTM3OQpGcmFtZXMgb3ZlciAxMDAgbXM6IDQ5Ckxvbmdlc3QgY29uc2VjdXRpdmUgcnVuIG92ZXIgMzMuMzMgbXM6IDUxNCBmcmFtZXMKRXhjbHVkZWQgZ2FwcyBvdmVyIDEwMDAgbXM6IDUKRXhjbHVkZWQgZ2FwIHRpbWU6IDUwODQwLjc1MCBtcwpXb3JzdCBleGNsdWRlZCBnYXA6IDI3MjA4LjkxMyBtcwpJbml0aWFsIGxpbmVhciBtZW1vcnkgZnJlZTogMzE0MDQwMzIgYnl0ZXMKTG93ZXN0IHNhbXBsZWQgbGluZWFyIG1lbW9yeSBmcmVlOiAyMjQ5OTg0MCBieXRlcwpDaXRybzNEIGNvbW1hbmQgYnVmZmVyIHNpemU6IDUyNDI4OCBieXRlcwpDb21tYW5kLWJ1ZmZlciB1c2FnZSBzYW1wbGVzOiA3MDI1CkNvbW1hbmQtYnVmZmVyIGxhc3QgdXNhZ2U6IDAuNTIyICUKQ29tbWFuZC1idWZmZXIgcGVhayB1c2FnZTogMzAuNTg4ICUKQ29tbWFuZC1idWZmZXIgcGVhayBlc3RpbWF0ZWQgYnl0ZXM6IDE2MDM2OApDaXRybzNEIHByZXNlbnRlZCBmcmFtZXM6IDcwMjUKQ2l0cm8zRCB1cGxvYWQgZmFpbHVyZXM6IDAKQ2l0cm8zRCBkcmF3IGZhaWx1cmVzOiAwCkxhc3Qgc2FtcGxlZCAzRCBzbGlkZXI6IDEuMDAwCkNsZWFuIFNodXRkb3duOiBZRVMKPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09Cg=='}
EVIDENCE_SHA={'C3D_RUN_R3D7C_1786136661_000000A90E3ACF6E_STARTED.txt': 'a0ac7eef98b8a9df5a730ab28a91c878d9cb46cd4975fb51b70deabe5da487be', 'C3D_RUN_R3D7C_1786136661_000000A90E3ACF6E_DEPTH_PROOF.log': '7cb39f02a3178b4b8804d09dff37e98c791a524c5557b58cd2fb55db3a31b9b6', 'C3D_RUN_R3D7C_1786136661_000000A90E3ACF6E_DIAG.log': '401822d3d352214d02fc37f577371e6b2d22383b7e739260637007ff77b1e417'}

BINMARKS=(
b"CITADEL-C3D-R3D7C-CMDBUF512-SHIPRC1",
b"PROJECT CITADEL C3D R3D7C CMDBUF512 SHIPRC1 ACTIVE",
b"RIGHT_ONLY_RECIPROCAL_W_DEPTH_WARP",
b"ONE_FR_REND_ONLY",
b"V2.0.0_SHIP_CANDIDATE_HARDENING",
)
FINAL_TOOLS={
"SEAL_CITADEL_R3D7B_AND_BUILD_V2RC1_CMDBUF512.py",
Path(__file__).name,
}
RUN_PREFIX=("RUN_","RUNONCE_","RUN_ONCE_","SEAL_","FIX_","RESUME_","CHECKPOINT_","PRESERVE_","ROLLBACK_","APPLY_","apply_Project_")
DROP_DIR={".git",".svn",".hg",".idea",".vscode","__pycache__"}
DROP_EXT={".o",".obj",".d",".pyc",".pyo",".bak",".tmp",".temp",".dmp"}
PUBLIC_BLOCK={".cia",".elf",".exe",".dll",".sit",".o",".obj",".d",".lib",".pdb",".zip",".7z",".rar",".tar",".gz",".sf2",".xmi",".mid",".midi",".wav",".mp3",".ogg",".flac",".res",".dat",".gam",".ark",".crf",".kpf",".dmp",".log"}

def die(s):
    print("\nERROR:",s,file=sys.stderr)
    print("No existing Project Citadel material was moved or deleted.")
    raise SystemExit(1)

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def wt(p,s):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(s.rstrip()+"\n",encoding="utf-8",newline="\n")

def runner(p):
    if p.name in FINAL_TOOLS: return False
    if p.suffix.lower()!=".py": return False
    return p.name.startswith(RUN_PREFIX) or ("r3d" in p.name.lower() and any(x in p.name.lower() for x in ("patch","apply","runner","checkpoint","seal")))

def report_render_hash():
    if not REPORT.is_file(): die("Final R3D7C stage report missing: "+str(REPORT))
    t=REPORT.read_text(encoding="utf-8",errors="replace")
    for x in (MILESTONE,SHOCK,FRSETUP,"Citro3D command buffer 0x40000 -> 0x80000"):
        if x not in t: die("Final stage report identity mismatch: "+x)
    m=re.search(r"render\.c\s+([0-9a-fA-F]{64})",t)
    if not m: die("Could not extract exact render.c hash from stage report.")
    return m.group(1).lower()

def verify_source():
    if not SRC.is_dir() or not SDL.is_dir(): die("Current R3D7 source/SDL2 tree missing.")
    exact={"src/MacSrc/Shock.c":SHOCK,"src/GameSrc/frsetup.c":FRSETUP,"src/GameSrc/render.c":report_render_hash(),**COMP}
    bad=[]
    for r,e in exact.items():
        q=SRC/r
        if not q.is_file() or sha(q)!=e: bad.append(r)
    if bad: die("Current source is not exact tested R3D7C:\n  "+"\n  ".join(bad))
    rt=(SRC/"src/GameSrc/render.c").read_text(encoding="utf-8",errors="replace")
    a=rt.find("PROJECT CITADEL C3D R3D7A AVP STEREO PARITY1"); b=rt.find("citadel_3ds_stereo_end_frame();",a)
    block=rt[a:b]
    if a<0 or b<0 or block.count("fr_rend(NULL);")!=2 or "citadel_3ds_stereo_begin_right_pass();" in block:
        die("One-traversal scheduler semantic verification failed.")
    for q in (SDL/"include/SDL.h",SDL/"build-3ds/libSDL2.a",SDL/"build-3ds/libSDL2main.a"):
        if not q.is_file(): die("Required SDL2 dependency missing: "+str(q))
    print("PASS: exact current R3D7C source + dependency.")
    return exact

def verify_binary():
    if not BIN.is_file(): die("Final tested binary missing: "+str(BIN))
    d=BIN.read_bytes()
    miss=[x for x in BINMARKS if x not in d]
    if miss: die("Final binary marker verification failed.")
    info={"path":str(BIN),"size":BIN.stat().st_size,"sha256":sha(BIN)}
    print("PASS: final tested binary:",info["sha256"])
    return info

def get_evidence():
    out={}
    for n,e in EVIDENCE.items():
        d=base64.b64decode(e)
        if hashlib.sha256(d).hexdigest()!=EVIDENCE_SHA[n]: die("Embedded evidence hash mismatch: "+n)
        out[n]=d
    j=b"\n".join(out.values())
    req=(b"R3D7C ship-candidate renderer path proven: YES",b"Mono average FPS: 30.832",b"Stereo average FPS: 23.836",b"Command-buffer peak usage: 30.588 %",b"GPU draw failures: 0",b"Clean Shutdown: YES")
    if any(x not in j for x in req): die("Embedded final hardware evidence content mismatch.")
    print("PASS: final R3D7C hardware evidence.")
    return out

def common_keep(p,rel):
    if any(x in DROP_DIR for x in rel.parts): return False
    if p.suffix.lower() in DROP_EXT: return False
    if p.name.startswith("C3D_RUN_"): return False
    return True

def ours_keep(p,rel):
    if not common_keep(p,rel): return False
    if runner(p): return False
    for part in rel.parts:
        low=part.lower()
        if low=="build" or low.startswith("cmake-build") or "checkpoint" in low or "stereobackup" in low: return False
    return True

def public_keep(p,rel):
    if not ours_keep(p,rel): return False
    if p.suffix.lower() in PUBLIC_BLOCK: return p.name in {"Hack-i-Ben_Splash.t3x","V15H_CONTROL.t3x"}
    if p.name in {"relocations.txt","sections.txt","symbols.txt","systemshock.exe","ShockMac.sit"}: return False
    return True

def copy_filtered(src,dst,keep):
    c=0; z=0
    for root,dirs,files in os.walk(src,topdown=True):
        rp=Path(root)
        dirs[:]=[x for x in dirs if keep(rp/x,(rp/x).relative_to(src))]
        for n in files:
            s=rp/n; rel=s.relative_to(src)
            if not keep(s,rel): continue
            d=dst/rel; d.parent.mkdir(parents=True,exist_ok=True)
            if s.is_symlink():
                wt(d.with_suffix(d.suffix+".SYMLINK.txt"),"Original symlink: "+str(s)+"\nTarget: "+os.readlink(s))
            else:
                shutil.copy2(s,d); z+=s.stat().st_size
            c+=1
    return c,z

def find_asset(name):
    found=[]
    for r in (SRC,DEV):
        if r.exists():
            for q in r.rglob(name):
                if q.is_file(): found.append(q)
    if not found:return None
    found.sort(key=lambda q:("build" in [x.lower() for x in q.parts],len(q.parts),str(q)))
    return found[0]

def build_ours(exact,bininfo,evd):
    print("\n===== 01_FOR_US_MASTER =====")
    proj=OURS/"CURRENT_PROJECT"
    sc,sb=copy_filtered(SRC,proj/"Source/shockolate",ours_keep)
    dc,db=copy_filtered(SDL,proj/"Libraries/SDL2",lambda p,r:common_keep(p,r))
    for n in ("R3D7_AVP_STEREO_BRANCH.txt","R3D7_EXTERNAL_DEPENDENCIES.json"):
        q=DEV/n
        if q.is_file(): shutil.copy2(q,proj/n)
    art=OURS/"FINAL_ARTIFACTS"; art.mkdir(parents=True)
    shutil.copy2(BIN,art/"3D_Citadel_3DS.3dsx"); shutil.copy2(BIN,art/"3D_Citadel_3DS_v2.0.0.3dsx")
    shutil.copy2(REPORT,art/REPORT.name)
    e=OURS/"FINAL_HARDWARE_EVIDENCE";e.mkdir()
    for n,d in evd.items():(e/n).write_bytes(d)
    tools=OURS/"FINAL_BUILD_TOOLS";tools.mkdir()
    for n in FINAL_TOOLS:
        choices=[SRC/n,Path.cwd()/n]
        if Path(__file__).name==n: choices.append(Path(__file__).resolve())
        for q in choices:
            if q.is_file(): shutil.copy2(q,tools/q.name);break
    ext=OURS/"EXTERNAL_FOR_US_ITEMS"
    copied=[]
    pats=("for_us","for-us","for us","forus")
    for q in P.iterdir():
        low=q.name.lower()
        if q==SHIP or "citadel" not in low or not any(x in low for x in pats): continue
        if q==DEV: continue
        copied.append(str(q))
        if q.is_dir(): copy_filtered(q,ext/q.name,lambda p,r:common_keep(p,r))
        else: (ext).mkdir(parents=True,exist_ok=True);shutil.copy2(q,ext/q.name)
    wt(OURS/"HOTFIX_START_HERE.md",f"""# Project Citadel 3DS {VER} — hotfix start

Authoritative frozen renderer: `{MILESTONE}`.

Do **not** patch this shipped folder in place. For any future reproducible user
issue, copy `CURRENT_PROJECT/` to a new hotfix worktree and compare against
`FINAL_ARTIFACTS/3D_Citadel_3DS.3dsx` and `FINAL_HARDWARE_EVIDENCE/`.

Qualified baseline: 30.832 FPS mono, 23.836 FPS true stereo, 512 KiB command
buffer with 30.588% peak use, 22,499,840 bytes minimum sampled linear memory,
zero renderer failure counters, clean shutdown.
""")
    return {"source_files":sc,"source_bytes":sb,"sdl_files":dc,"sdl_bytes":db,"external_for_us":copied,"exact_source":exact,"binary":bininfo}

def public_sdl(dst):
    c,z=copy_filtered(SDL/"include",dst/"include",lambda p,r:common_keep(p,r))
    (dst/"build-3ds").mkdir(parents=True,exist_ok=True)
    libs={}
    for n in ("libSDL2.a","libSDL2main.a"):
        s=SDL/"build-3ds"/n
        if not s.is_file():die("Missing SDL2 library: "+str(s))
        d=dst/"build-3ds"/n;shutil.copy2(s,d);libs[n]=sha(d);c+=1;z+=d.stat().st_size
    for n in ("LICENSE.txt","LICENSE","COPYING.txt"):
        s=SDL/n
        if s.is_file():shutil.copy2(s,dst/n)
    wt(dst/"CITADEL_3DS_DEPENDENCY_README.txt","Exact SDL2 headers and manually-built 3DS static libraries used by Project Citadel 3DS v2.0.0.\nCMake expects this at ../../Libraries/SDL2 relative to Source/shockolate.")
    return {"files":c,"bytes":z,"libraries":libs}

def build_github(bininfo):
    print("\n===== 02_GITHUB_DISTRIBUTION =====")
    sc,sb=copy_filtered(SRC,GH/"Source/shockolate",public_keep)
    sdl=public_sdl(GH/"Libraries/SDL2")
    rel=GH/"Release";rel.mkdir(parents=True)
    shutil.copy2(BIN,rel/"3D_Citadel_3DS.3dsx")
    assets=[]
    for n in ("Hack-i-Ben_Splash.t3x","V15H_CONTROL.t3x"):
        q=find_asset(n)
        if q:shutil.copy2(q,rel/n);assets.append(n)
    for n in ("Project_Citadel_GitHub_Hero_1200x630.png","Project_Citadel_Icon_512.png","Hack-i-Ben_Splash.png"):
        q=find_asset(n)
        if q:(GH/"assets").mkdir(exist_ok=True);shutil.copy2(q,GH/"assets"/n);assets.append("assets/"+n)
    wt(GH/"README.md",f"""# Project Citadel 3DS

A native Nintendo 3DS port of **System Shock (1994)** based on Shockolate.

## {VER} — shipped

The v2 renderer uses native Citro3D world rendering plus the AvP-style
single-stream stereo architecture: one engine scene traversal per stereo
frame, the same native scene sent to both physical eyes, a right-eye
reciprocal-depth warp for real station-world depth, and a flat zero-parallax
HUD/interface.

Final representative New Nintendo 3DS qualification:
- **30.832 FPS mono** over 3,837 measured frames;
- **23.836 FPS true stereo** over 3,182 measured frames;
- 512 KiB command buffer, **30.588%** peak usage;
- zero capture overflow, draw-budget, upload, presentation, or GPU failures;
- clean shutdown.

Lighter stereo workloads during development reached roughly 28–32 FPS.

## Original game data required

Copyrighted System Shock game data is **not included**. Provide legally obtained
game data in `sdmc:/3ds/SystemShock3D/`. See `INSTALLING.md`.

## Project status

Renderer development is frozen at v2.0.0. Future work is limited to focused
hotfixes for reproducible user-facing issues.

System Shock and related names/assets belong to their respective owners.
Project Citadel 3DS is an independent fan preservation/porting project.
""")
    wt(GH/"BUILDING_3DS.md","""# Building v2.0.0

Requirements: devkitPro/devkitARM with 3DS libraries, CMake, and an MSYS2/devkitPro or compatible shell.

The exact qualified SDL2 headers/static libraries are included in `Libraries/SDL2`.

```bash
export DEVKITPRO=/opt/devkitpro
export DEVKITARM=/opt/devkitpro/devkitARM
cd Source/shockolate
rm -rf build
cmake -S . -B build \
  -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DENABLE_OPENGL=OFF \
  -DENABLE_SOUND=OFF \
  -DENABLE_FLUIDSYNTH=OFF \
  -DENABLE_SDL2=ON
cmake --build build --target project_citadel_3dsx -j"$(nproc)"
```

Qualified release executable: `Release/3D_Citadel_3DS.3dsx`.
""")
    wt(GH/"INSTALLING.md","""# Installing v2.0.0

Copy the release executable and included Project Citadel presentation assets to:

```text
sdmc:/3ds/SystemShock3D/
├── 3D_Citadel_3DS.3dsx
├── Hack-i-Ben_Splash.t3x
├── V15H_CONTROL.t3x
├── DATA/
├── RES/
└── SOUND/
```

`DATA`, `RES`, and `SOUND` must come from a legally obtained original game copy.
Launch `3D_Citadel_3DS.3dsx` from the Homebrew Launcher.

Slider down is mono; raising the slider progressively adds station-world depth.
The HUD/interface stays flat for readability.
""")
    wt(GH/"RELEASE_NOTES_v2.0.0.md",f"""# Project Citadel 3DS {VER}

Frozen renderer: `{MILESTONE}`

- one `fr_rend()` traversal per stereo frame;
- same native scene stream drives both eyes;
- right-only reciprocal-W depth warp;
- flat shared HUD/foreground;
- no right software residual/framebuffer reconstruction/legacy compositor;
- 512 KiB Citro3D command buffer.

Final hardware run `{TOKEN}`:
- mono 30.832 FPS;
- stereo 23.836 FPS;
- 3,060 stereo scene traversals and 3,060 physical-right engine traversals skipped;
- 516,324 right-eye depth-warp vertices;
- 30.588% peak command-buffer use (~160,368 bytes);
- lowest sampled linear free memory 22,499,840 bytes;
- zero renderer failures;
- clean shutdown.

Renderer chapter closed. Future changes are issue-specific hotfixes only.
""")
    wt(GH/"KNOWN_ISSUES.md","""# Known issues / support policy

No renderer-blocking issue was identified in the final v2.0.0 hardware qualification.

The renderer is frozen. Future changes should be made only for a reproducible
user-facing problem that warrants a focused hotfix. Include the generated
diagnostic log with reports when available.
""")
    wt(GH/".gitignore","""build/
cmake-build*/
*.o
*.obj
*.d
*.pyc
__pycache__/
*.log
*.dmp
*.bak
*.tmp
C3D_RUN_*
""")
    sums=[]
    for q in sorted(rel.rglob("*")):
        if q.is_file():sums.append(f"{sha(q)}  {q.relative_to(GH).as_posix()}")
    wt(GH/"SHA256SUMS_RELEASE.txt","\n".join(sums))
    bad=[str(q.relative_to(GH)) for q in GH.rglob("*") if q.is_file() and q.suffix.lower() in {".res",".dat",".gam",".ark",".crf",".kpf",".wav",".mp3",".ogg",".flac"}]
    if bad:die("Public GitHub tree contains retail-data-like files:\n  "+"\n  ".join(bad))
    return {"source_files":sc,"source_bytes":sb,"sdl":sdl,"binary_sha256":bininfo["sha256"],"assets":assets}

def archive_candidates():
    x=[str(q) for q in sorted(P.iterdir(),key=lambda z:z.name.lower()) if q!=SHIP and "citadel" in q.name.lower()]
    wt(READ/"ARCHIVE_CANDIDATES_AFTER_V2_FREEZE.txt","""PROJECT CITADEL ARCHIVE CANDIDATES AFTER v2.0.0 FREEZE
========================================================

These Project-Citadel-named items remain OUTSIDE the authoritative shipped
folder. Nothing was moved or deleted. After reviewing the new shipped folder,
these are the historical materials to ZIP/archive before cleaning /c/Projects.

"""+("\n".join(x) if x else "(none)"))
    return x

def manifest(root,out):
    rows=[];total=0
    for q in sorted(root.rglob("*")):
        if q.is_file() and q!=out:
            z=q.stat().st_size;total+=z
            rows.append({"path":q.relative_to(root).as_posix(),"size":z,"sha256":sha(q)})
    wt(out,json.dumps({"root":str(root),"file_count":len(rows),"total_bytes":total,"files":rows},indent=2))
    return {"file_count":len(rows),"total_bytes":total}

def main():
    print("="*78);print("PROJECT CITADEL 3DS — FINAL v2.0.0 FREEZE");print("="*78)
    if SHIP.exists():die("Destination already exists; refusing to merge/overwrite:\n  "+str(SHIP))
    exact=verify_source();bininfo=verify_binary();evd=get_evidence()
    SHIP.mkdir();READ.mkdir();OURS.mkdir();GH.mkdir();EVD.mkdir();MAN.mkdir()
    for n,d in evd.items():(EVD/n).write_bytes(d)
    wt(EVD/"EVIDENCE_SHA256.txt","\n".join(f"{EVIDENCE_SHA[n]}  {n}" for n in sorted(EVIDENCE_SHA)))
    oi=build_ours(exact,bininfo,evd);gi=build_github(bininfo)
    # Exact critical-copy verification.
    for r,h in exact.items():
        for root in (OURS/"CURRENT_PROJECT/Source/shockolate",GH/"Source/shockolate"):
            q=root/r
            if not q.is_file() or sha(q)!=h:die("Frozen source copy mismatch: "+str(q))
    for q in (OURS/"FINAL_ARTIFACTS/3D_Citadel_3DS.3dsx",GH/"Release/3D_Citadel_3DS.3dsx"):
        if sha(q)!=bininfo["sha256"]:die("Frozen binary copy mismatch: "+str(q))
    cand=archive_candidates()
    wt(READ/"PROJECT_CITADEL_V2.0.0_SHIPPED.txt",f"""PROJECT CITADEL 3DS — {VER} SHIPPED
======================================

External release: Project Citadel 3DS {VER}
Frozen tested renderer: {MILESTONE}
Final run: {TOKEN}

FINAL QUALIFIED RESULT
----------------------
Mono: 3837 frames, 30.832 FPS.
True stereo: 3182 frames, 23.836 FPS.
One scene traversal per stereo frame; same native stream drives both eyes.
Right-only reciprocal-W world-depth warp; flat HUD/foreground.
512 KiB command buffer; 30.588% peak (~160368 bytes).
Lowest sampled linear free memory: 22499840 bytes.
Zero renderer failure counters. Clean shutdown.

AUTHORITATIVE CONTENT
---------------------
01_FOR_US_MASTER/       immutable rebuild/hotfix master
02_GITHUB_DISTRIBUTION/ clean public {VER} tree
03_FINAL_EVIDENCE/      exact final hardware logs
04_MANIFESTS/           recursive SHA-256 inventories

ARCHIVE POLICY
--------------
Review this folder first. Then ZIP the old Project Citadel items listed in
00_READ_ME_FIRST/ARCHIVE_CANDIDATES_AFTER_V2_FREEZE.txt and clean them from the
live /c/Projects workspace if desired. Do not permanently delete the archive.

FUTURE POLICY
-------------
Project Citadel renderer development is CLOSED. Future work begins from the
FOR_US master only when a reproducible user issue warrants a focused hotfix.
""")
    wt(READ/"GITHUB_TOMORROW.txt","""GitHub-ready tree:
  02_GITHUB_DISTRIBUTION/

Before publishing: review docs, verify SHA256SUMS_RELEASE.txt, confirm no
licensed DATA/RES/SOUND were added, then commit/tag v2.0.0 and create the
release using Release/3D_Citadel_3DS.3dsx and included presentation assets.

A reminder is scheduled for Sunday at 3:00 PM local time.
""")
    wt(MAN/"V2_SHIP_FREEZE.json",json.dumps({"version":VER,"renderer":MILESTONE,"run":TOKEN,"created":dt.datetime.now().astimezone().isoformat(),"source_hashes":exact,"binary":bininfo,"for_us":oi,"github":gi,"archive_candidates":cand,"status":"FROZEN_SHIPPED_HOTFIX_ONLY"},indent=2))
    a=manifest(OURS,MAN/"FOR_US_MASTER_FILES.json");g=manifest(GH,MAN/"GITHUB_DISTRIBUTION_FILES.json");e=manifest(EVD,MAN/"FINAL_EVIDENCE_FILES.json")
    wt(READ/"FREEZE_COMPLETE.txt",f"""PASS: PROJECT CITADEL 3DS {VER} FREEZE COMPLETE

Authoritative folder:
  {SHIP}

Final binary SHA-256:
  {bininfo['sha256']}

FOR_US: {a['file_count']} files / {a['total_bytes']} bytes
GitHub: {g['file_count']} files / {g['total_bytes']} bytes
Evidence: {e['file_count']} files / {e['total_bytes']} bytes

STATUS: CLOSED / SHIPPED / HOTFIX-ONLY.
""")
    manifest(SHIP,MAN/"WHOLE_V2_SHIP_FILES.json")
    print("\n"+"="*78);print("PASS: PROJECT CITADEL 3DS v2.0.0 — FROZEN / SHIPPED");print("="*78)
    print("KEEP:",SHIP);print("GITHUB:",GH);print("FOR US:",OURS)
    print("ARCHIVE LIST:",READ/"ARCHIVE_CANDIDATES_AFTER_V2_FREEZE.txt")
    print("No existing Project Citadel material was moved or deleted.")
    return 0

if __name__=="__main__":raise SystemExit(main())
