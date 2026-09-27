# Version 3.3.0 verification — 2026-09-27

Test host: macOS, Apple M5 Pro, 18 logical CPU cores, 48 GiB RAM.

| Check | Result |
| --- | --- |
| Pure Python reader tests | 10 passed |
| Blender 4.5.12 LTS integration | Passed |
| Blender 5.2.0 LTS integration | Passed |
| Blender 5.2 foreground modal clean/export | Passed |
| Blender 5.2 foreground Undo and simulated Esc | Passed |
| Blender extension ZIP validation | Passed |

Integration checks exercise actual geometry changes, Cycles CPU baking and
packed red/green image pixels, multi-process OBJ and FBX exports, texture/MTL
references, relative export directories, sanitized filename collisions,
parent/world transforms, object identities, backups, shared meshes/materials,
one failing object among successful objects, cancellation and process cleanup.
Single-object cleaning, meshes without color attributes, POINT color attribute
conversion, Shared UVs, manual 2-Step Clean, CPU fallback with no active GPU,
render-setting restoration, and unregister/register also pass.

MagicaVoxel 0.99.6.2 macOS distribution: all 15 local VOX files parse as VOX 150.
The bundled `3x3x3.vox`, `8x8x8.vox`, and `chr_knight.vox` pass import → parallel
clean/bake → OBJ/FBX export on both Blender versions. Generated VOX 200 fixtures
pass the same integration checks. Three additional local project files (two
VOX 150 and one VOX 200) pass parsing; this is not a full scene fidelity check.

Controlled timing on Blender 5.2, four copies of the bundled `chr_knight.vox`,
geometry cleanup plus the five imported material maps, with identical output
vertex counts (416 per model):

| Worker processes | Total wall time, including startup/transfer | Relative speed |
| --- | ---: | ---: |
| 1 | 5.161 s | 1.00× |
| 2 | 2.655 s | 1.94× |

This is one local workload and one run per setting, not a general speedup
guarantee. No GPU performance result is claimed. Blender 4.2 remains the declared
minimum but was not installed for runtime verification. Tests used isolated
Blender instances; no installed Pro add-on or existing user scene was replaced.

Reproduction commands are in the main README. Tests write detailed reports and
outputs to a temporary directory printed as `VOX_INTEGRATION_PASS` or
`VOX_UI_PASS`; expected failing-job tracebacks in an integration log are part of
the failure-isolation test.
