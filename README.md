
# Vox Cleaner V3
Voxel Model Importer, Cleaner & Exporter, an add-on for Blender 4.2+!
---------------------------------------------------------------------------------------

## Fork version 3.3.0

- Imports both VOX 150 (including MagicaVoxel 0.99.6 / 0.99.6.2 for macOS) and VOX 200. Handles files without a scene graph, optional default palettes, PACK models, old MATT and newer MATL materials, layers and nested transforms. Animated scenes import their first frame as static meshes.
- Supports Blender 5.2. Runtime checks cover Blender 4.5.12 LTS and 5.2.0 LTS; the extension minimum remains 4.2.
- Select multiple meshes and click the existing **Clean**, **OBJ**, or **FBX** button. Cleaning gives each object its own UVs/textures; exporting writes one file per object. No separate batch buttons are added.
- **Shared UVs** still combines the selected meshes into one texture atlas. The interactive **2-Step Clean** workflow operates on one model or one Shared UV group.

### Batch processing

Independent objects run in separate background Blender processes. CPU cores are divided between workers, with an automatic memory budget. **General Settings → Parallel workers** defaults to `0` (automatic, up to eight processes); `1` runs jobs sequentially. This limit is a memory estimate, not a guarantee for arbitrarily large scenes. Large textures and modifier dependencies may need a lower worker count.

Geometry processing uses the CPU. Texture baking uses Cycles: single-object cleaning honors the scene's CPU/GPU setting and falls back to CPU when no GPU device is active; batch workers use CPU to avoid competing for GPU memory. Small jobs can take longer because starting background Blender processes has overhead.

Progress appears in Blender's status bar. **Esc** stops pending/running jobs and retains completed results. A failed object is reported while the others continue. Successful cleaning preserves object identities, transforms, parent relationships and selection; backups follow the existing backup setting. Clean results support Blender Undo. Exported files are external outputs and are not undone by Blender Undo.

OBJ/FBX and texture filenames are sanitized, and collisions between selected names receive numbered suffixes. Existing files with the resulting names are replaced on subsequent exports. Textures shared by multiple objects are saved once before the export workers start.

### Install and verify

Build the installable extension with Python 3.9+:

```sh
python3 scripts/package_addon.py
```

In Blender, open **Preferences → Add-ons → Install from Disk** and choose the newly built `dist/vox-cleaner-3.3.0.zip` or the saved `release/voxel-cleaner-3.3.0.zip`. The original `release/Vox_Cleaner_V3.1.zip` and `release/Vox_Cleaner_V3.2.zip` archives are unchanged upstream releases, not this build.

Tests:

```sh
python3 -m unittest discover -s tests -v
blender --background --factory-startup --threads 4 --python-exit-code 1 --python tests/blender_integration.py
blender --factory-startup --enable-event-simulate --threads 4 --python tests/blender_ui.py
```

Set `VOX_SAMPLES_DIR` to the `vox` folder in a MagicaVoxel 0.99.6.2 distribution to include its real sample models in the integration run. The foreground test starts from factory settings and quits its own Blender instance. Run it in a separate test process, not inside an existing working session.

The tests check import, actual baked pixel colors, batch OBJ/FBX files, parent transforms, backups, shared textures, independent failures, cancellation, Shared UV/2-Step compatibility, and the foreground modal/Undo workflow. The binary reader tests include malformed and truncated files.




## How does the cleaning procedure work:

1. **Type Checking & Basic Model fixing** - Remove doubles, etc is done so the model is in cleanable condition
2. **Model Fixing** - The complete model fixing happens here, along with Model duplication. A copy of the model is made so that the colors can be transferred from the copy to the cleaned model.
3. **Material setup** - The materials created & edited based on all the material maps that need to be baked, which are present in the Duplicated model from the Previous step
4. **UV projection** - UVs are projected using Blender's Cube project method and then packed. 
5. **Geo Cleanup** - Blender's Decimate modifier is used to shave off excess geometry. This process destroys the colors on the model.
6. **UV Scaling** - calculation of a rescale factor upto 9 decimals, & then scaling the UVs by the rescale factor to achieve pixel perfect UVs
7. **Texture baking** - using Blender's Cycles render engine. Bakes all the material maps needed
8. **Done! Enjoy!**\
\
\
\
**Some other features -**
\
**Shared UV Clean** - All the models are joined, treated as a single Object for the whole process and Split up again. This leads them to have a single baked texture.
\
Besides this, there is a **2-Step Process** that provides more control over the UV process. 
\
\
This fork adds batch cleaning and batch exports to the open-source version. SubSurface support remains a feature of the upstream Pro version.
\
More Information on [My Website ](https://www.thestrokeforge.xyz/vox-cleaner)!
\
\
\
\
\
\
---------------------------------------------------------------------------------------\
Vox Cleaner's Importer is based on a custom, highly modified version of [the importer made by TechnistGuru](https://github.com/technistguru/MagicaVoxel_Importer). Thanks so much! (I tried to thank you personally but no response)

\
**Happy Cleaning! Cheers!** \
**Farhan, The Creator of Vox Cleaner**
