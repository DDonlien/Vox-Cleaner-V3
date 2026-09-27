
#   ██╗░░░██╗░█████╗░██╗░░██╗   ░█████╗░██╗░░░░░███████╗░█████╗░███╗░░██╗███████╗██████╗░    ██╗░░░██╗██████╗░
#   ██║░░░██║██╔══██╗╚██╗██╔╝   ██╔══██╗██║░░░░░██╔════╝██╔══██╗████╗░██║██╔════╝██╔══██╗    ██║░░░██║╚════██╗
#   ╚██╗░██╔╝██║░░██║░╚███╔╝░   ██║░░╚═╝██║░░░░░█████╗░░███████║██╔██╗██║█████╗░░██████╔╝    ╚██╗░██╔╝░░███╔═╝
#   ░╚████╔╝░██║░░██║░██╔██╗░   ██║░░██╗██║░░░░░██╔══╝░░██╔══██║██║╚████║██╔══╝░░██╔══██╗    ░╚████╔╝░░░╚══██╗
#   ░░╚██╔╝░░╚█████╔╝██╔╝╚██╗   ╚█████╔╝███████╗███████╗██║░░██║██║░╚███║███████╗██║░░██║    ░░╚██╔╝░░██████╔╝
#   ░░░╚═╝░░░░╚════╝░╚═╝░░╚═╝   ░╚════╝░╚══════╝╚══════╝╚═╝░░╚═╝╚═╝░░╚══╝╚══════╝╚═╝░░╚═╝    ░░░╚═╝░░░╚═════╝░
#
#                                                    █▄▄ █▄█   █▀▀ ▄▀█ █▀█ █ █ ▄▀█ █▄ █   █▀ █ █ ▄▀█ █ █▄▀ █ █
#                                                    █▄█  █    █▀  █▀█ █▀▄ █▀█ █▀█ █ ▀█   ▄█ █▀█ █▀█ █ █ █ █▀█
#

'''
VoxCleaner © 2024 by Farhan Shaikh is licensed under GPL 3.0 or later. 

License: GPL 3.0 or later
Everyone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed. Giving credit to the Creator is appreciated but not required.
Read more about the license: https://spdx.org/licenses/GPL-3.0-or-later.html

Thanks so much for your purchase and please feel free to tag me @TheStrokeForge on Instagram/Twitter & I’d love to see your work! Cheers!

''' 

import os, sys, subprocess

import math
import numpy as np
import struct
from decimal import Context
from logging import error, exception

import bpy
import bmesh
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, CollectionProperty, EnumProperty
from bpy.types import Operator
from mathutils import Matrix

import webbrowser

from . import batch
from .vox_format import read_vox

class FlowData:
    ModelType = None
    MainObj = 0
    MainObjName = None
    DupeObj = 0
    DupeObjName = None
    ObjArray = None
    CommonUVObjects = []
    CommonUVDupeObjects = []
    CommonUVOrigins = {}

    VertexCountInitialX = 0
    VertexCountFinalX = 0

    SmallestEdge = None
    SmallestEdgeLength = 10000000.0

    LargestEdge = None
    LargestEdgeLength = 0.0
    LargestEdgeBlocks = 0
    LargestUVEdgeLengthInPixels = 0.0
    ResizeFactor = 0.0

    ApproxLen = 0.0
    AutoRes = 0
    FinalTextureSize = 0.0
    Bleed = 0.0

    MaterialMaps = []
    GeneratedTex_Active = None
    BakeList = []
    
    GeneratedTex_Color = None
    GeneratedTex_Roughness = None
    GeneratedTex_Metallic = None
    GeneratedTex_Emisson = None
    GeneratedTex_Transmission = None
    
    BakeTimes = 0
    CleanTimes = 0
    CleanType = None
    TwoStepCommonUV = False
    ProcessRunning = False
    MissingActors = False

    ImportNameIndex = 0
 

class StaticData:
    #Default Numbers ----------------------------------------
    StandardBakeResolutions = [8,16,32,64,128,256,512,1024,2048,4096,8192]
    TriangulateLoops = 8
    
    #Default Preferences ---------------------------------------
    # Importer
    RoughnessDefault = 0.5   # default roughness for diffuse materials
    
    # Cleaner
    ResolutionDefault = "Mini"
    UpscalingDefault = "1"
    UVMethodDefault = "cube"
    RotateUVDefault = False
    MCNVResDefault = "1024"
    NVDecimationDefault = 70

    BaseColorDefault = (0.6,0.0,0.2,1.0)
    AlphaDefault = False
    EmitStrengthDefault = 8.0

    ModelBackupDefault = True
    OrganiseDefault = True  # Organise model backups

    # Exporter
    TriangulateDefault = True

    #UI Data --------------------------------------------------
    BigButtonHeight = 1.5
    ButtonHeightMedium = 1.2
    CleanModePaneHeight = 1

    RowSpacing = 1

    SeperatorSpacing1 = 0.5
    SeperatorSpacing2 = 0.2
    SeperatorSpacing3 = 0.1
    SeperatorSpacing4 = 0.05

    VerticalSplitFactor = 0.5


class VoxProperties(bpy.types.PropertyGroup):
    BatchWorkers: IntProperty(name="Parallel workers", default=0, min=0, max=64,
        description="0: automatic CPU and memory budget. 1: sequential background jobs. Each worker runs an isolated Blender process")

    # Clean related ###########################################################################################################################################################################################################################
    BaseColor : bpy.props.FloatVectorProperty(name='',subtype='COLOR_GAMMA',size=4, min=0.0, max=1.0, precision=4, default = StaticData.BaseColorDefault, description="""Base color of the generated image.
Set this to white before cleaning, if you wish to pixel texture paint on the model!

Ps, This color won't be visible on the final cleaned model, is just for easier visibility""") # type: ignore
    
    ResolutionSet : bpy.props.EnumProperty(
        name = "",default = StaticData.ResolutionDefault,
        items = [("Stan", "8,16,32,64,128...", "The Set of Standard image sizes like [8,16,32,64,128,256...]"),
                 ("Mini", "Smallest Possible", "The smallest image size possible, not following any set.")],
        description="""Resolution Set for Voxel Models.
"Smallest Possible" option for the smallest possible resolutions.
"8,16,32,64..." option for industry standard resolutions.

Selected Resolution Set""") # type: ignore
    
    #Scale multiplier for the baked texture
    TextureScaleMultiplier : bpy.props.EnumProperty(
        name = "",default= StaticData.UpscalingDefault,
        items = [("1", "1x", "", 0),
                 ("2", "2x", "", 2),
                 ("4", "4x", "", 4),
                 ("8", "8x", "", 8),
                 ("16", "16x", "", 16),
                 ("32", "32x", "", 32),
                 ("64", "64x", "", 64),],
        description="""Texture uspcaling for Voxel Models. 
More upscaling takes more time to clean. 

Current upscaling""") # type: ignore
    
    MCNVResolution : bpy.props.EnumProperty(
        name = "",default= StaticData.MCNVResDefault,
        items = [("64", "64 px", "", 1),
                 ("128", "128 px", "", 2),
                 ("256", "256 px", "", 3),
                 ("512", "512 px", "", 4),
                 ("1024", "1024 px", "", 5),
                 ("2048", "2048 px", "", 6),
                 ("4096", "4096 px", "", 7),
                 ("8192", "8192 px", "", 8)],
        description="""Texture Resolution for MC & Non-Voxel models. 
        
Selected Resolution""") # type: ignore
    
    CleanMode : bpy.props.EnumProperty(
        items = [("ez", "Lazy Clean", "Used for fast, one-click cleaning. Cleaned models have automatic Pixel-Perfect UVs", 1),
                 ("hard", "2-Step Clean", "Used on a single object for detail oriented cleaning. Allows you to have control over aspects like custom UVs.", 2),],
        description="""Mode of Cleaning.
● Use lazy clean for fast, one-click cleaning.
● Use 2-Step clean for more controlled cleaning like custom UVs.

Mode of cleaning you're hovering on""",default = "ez") # type: ignore
    
    UVMethod : bpy.props.EnumProperty(name = "",
        items = [("cube", "Cube (Recommended)", "The standard method for voxel UV projection. Might give some errors in very small models (15 voxels or less)", 1),
                 ("smart", "Smart", "Works better on small models when Cube projection fails", 2),],
        description="""UV Projection method used for Voxel models.
        
Choose 'Smart' ONLY when a model is showing errors with the Cube method. The 'Smart' method doesn't work very well on bigger models.

Usually such errors(like Overlapping UVs) are present only in pretty small models, making it a good place to try out the 'Smart' projection method!

UV Projection method you're hovering on""",default = "cube") # type: ignore
    
    NVDecimation : bpy.props.FloatProperty(name="", default=StaticData.NVDecimationDefault, subtype="PERCENTAGE",min=0.0, max=100.0, description="""Vertex Reduction Percentage for Non-Voxel Models.
More will result in more cleaning""") # type: ignore

    AlphaBool: bpy.props.BoolProperty(name="", default = False, description="Should the generated image have alpha?") # type: ignore
    
    CleanGeo: bpy.props.BoolProperty(name="Clean Geometry", default = True, description="""Clean Geometry while cleaning. 
Disable if you wish to preserve the geometry for better mesh flexing""") # type: ignore
    
    BakeTex: bpy.props.BoolProperty(name="Apply Texture", default = True, description="""Generate & bake textures while cleaning. 
Disable if you don't want textures or a material on your model""") # type: ignore
    
    CommonUV: bpy.props.BoolProperty(name="Shared UVs", default = False, description="""Shared UV Cleaning.
Enabling this will make all the selected models have a shared UV map layout after cleaning. Helpful if you want to have multiple objects having the same texture. 

E.g., You can use this option for a character with multiple parts. This way you'll have one texture for the entire character instead of having one texture for all of it's individual parts""") # type: ignore
    
    RotateUV: bpy.props.BoolProperty(name="", default = False, description="""Enables cardinal rotations of UV islands. 
Disabling will not rotate the UV islands
                                     
Affects only Voxel models""") # type: ignore

    EmitStrength : bpy.props.FloatProperty(name="", default=StaticData.EmitStrengthDefault,min=0.0, max=100.0, description="""Default emission strength if emission is enabled.
This can be tweaked later in the shader nodes""") # type: ignore

    CreateBackup: bpy.props.BoolProperty(name="Create model backup", default = StaticData.ModelBackupDefault, description="Enabling preserves a version of the original model in the scene") # type: ignore

    OrganiseBackups: bpy.props.BoolProperty(name="Organise backups into Collections", default = StaticData.ModelBackupDefault, description="""Enabling will organise your backups in a Blender collection 
called 'Vox Cleaner Backups', not cluttering your Blender outliner""") # type: ignore
    

    #Export related ######################################################################################################################################################################################################################################################
    ExportLocation : bpy.props.StringProperty(name="",default = "", description="Directory where your objects will be exported", subtype="DIR_PATH", options={"PATH_SUPPORTS_BLEND_RELATIVE"} if bpy.app.version >= (4, 5, 0) else set()) # type: ignore

    TriangulatedExport: bpy.props.BoolProperty(name="Export Triangulated model", default = StaticData.TriangulateDefault, description="Enabling triangulates the model before exporting. (Enabling is highly recommended)") # type: ignore
    
    
    
    ExportColor: bpy.props.BoolProperty(name="Color (C)", description="""Export color texture if available""", default = True) # type: ignore
    ExportRoughness: bpy.props.BoolProperty(name="Roughness (R)", description="""Export roughness texture if available""", default = True) # type: ignore
    ExportMetallic: bpy.props.BoolProperty(name="Metallic (M)", description="""Export metallic texture if available""", default = True) # type: ignore
    ExportEmission: bpy.props.BoolProperty(name="Emission (E)", description="""Export emission mask texture if available""", default = True) # type: ignore
    ExportTransmission: bpy.props.BoolProperty(name="Transmission (T)", description="""Export transparency mask texture if available""", default = True) # type: ignore
    

    # Import related #########################################################################################################################################################
    Organize: bpy.props.BoolProperty(name = "Organize into Collections", description = "Organize imported objects into collections based on their Vox file names", default = False) # type: ignore
    
    ImportHidden: bpy.props.BoolProperty(name = "Also import hidden objects", description = "Import hidden objects in the Vox file as well",default = True) # type: ignore
    
    OriginsAtBottom: bpy.props.BoolProperty(name = "Origins at bottom",description = "Set model origins at it's bottom-center. Disable to set origins in the center instead",default = True) # type: ignore

    MaxMaps: bpy.props.BoolProperty(name = "Max-out Material Properties",description = '''Materials Maps like Transmission, Emission etc perform much better in Blender if their values are set to 1 in MagicaVoxel.This checkbox does that automatically for you, saving you effort of going back and editing every material property in Magicavoxel.

Recommended for Materials containing Map Values like 0.1.

Affects: Emission & Transmission values''',default = False) # type: ignore
    
    ImportColor: bpy.props.BoolProperty(name="Color (C)", description="""Import color map""", default = True) # type: ignore
    ImportRoughness: bpy.props.BoolProperty(name="Roughness (R)", description="""Import roughness map""", default = True) # type: ignore
    ImportMetallic: bpy.props.BoolProperty(name="Metallic (M)", description="""Import metallic map""", default = True) # type: ignore
    ImportEmission: bpy.props.BoolProperty(name="Emission (E)", description="""Import emission map""", default = True) # type: ignore
    ImportTransmission: bpy.props.BoolProperty(name="Transmission (T)", description="""Import transparency map""", default = True) # type: ignore
    
class Vec3:
    def __init__(self, X, Y, Z):
        self.x, self.y, self.z = X, Y, Z
    
    def _index(self):
        return (self.x, self.y, self.z)

class VoxelObject:
    def __init__(self, Voxels, Size):
        self.size = Size
        self.voxels = {}
        self.used_colors = []
        self.position = Vec3(0, 0, 0)
        self.rotation = Vec3(0, 0, 0)
        
        for vox in Voxels:
            #              x       y       z
            pos = Vec3(vox[0], vox[1], vox[2])
            self.voxels[pos._index()] = (pos, vox[3])
            
            if vox[3] not in self.used_colors:
                self.used_colors.append(vox[3])
            
    
    def getVox(self, pos):
        key = pos._index()
        if key in self.voxels:
            return self.voxels[key][1]
        
        return 0
    
    def compareVox(self, colA, b):
        colB = self.getVox(b)
        
        if colB == 0:
            return False
        return True
    
    
    def generate(self, file_name, palette, materials, collections,TransformMatrix4x4):
        objects = []
        
        mytool = bpy.context.scene.vox_tool

        self.materials = materials  # For helper functions.
        
        mesh_col = collections
        
        if len(self.used_colors) == 0: # Empty Object
            return
        
        for Col in self.used_colors: # Create an object for each color and then join them.
            
            mesh = bpy.data.meshes.new(file_name) # Create mesh
            obj = bpy.data.objects.new(file_name, mesh) # Create object
            
            
            # Link Object to Scene
            if mesh_col == None:
                bpy.context.scene.collection.objects.link(obj)
            else:
                mesh_col.objects.link(obj)
            
            objects.append(obj) # Keeps track of created objects for joining.
            
            verts = []
            faces = []
            
            for key in self.voxels:
                pos, colID = self.voxels[key]
                x, y, z = pos.x, pos.y, pos.z
                
                if colID != Col:
                    continue
                
    
                            
                if not self.compareVox(colID, Vec3(x+1, y, z)):
                    verts.append( (x+1, y, z) )
                    verts.append( (x+1, y+1, z) )
                    verts.append( (x+1, y+1, z+1) )
                    verts.append( (x+1, y, z+1) )
                    
                    faces.append( [len(verts)-4,
                                    len(verts)-3,
                                    len(verts)-2,
                                    len(verts)-1] )
                
                if not self.compareVox(colID, Vec3(x, y+1, z)):
                    verts.append( (x+1, y+1, z) )
                    verts.append( (x+1, y+1, z+1) )
                    verts.append( (x, y+1, z+1) )
                    verts.append( (x, y+1, z) )
                    
                    faces.append( [len(verts)-4,
                                    len(verts)-3,
                                    len(verts)-2,
                                    len(verts)-1] )
                
                if not self.compareVox(colID, Vec3(x, y, z+1)):
                    verts.append( (x, y, z+1) )
                    verts.append( (x, y+1, z+1) )
                    verts.append( (x+1, y+1, z+1) )
                    verts.append( (x+1, y, z+1) )
                    
                    faces.append( [len(verts)-4,
                                    len(verts)-3,
                                    len(verts)-2,
                                    len(verts)-1] )
                
                if not self.compareVox(colID, Vec3(x-1, y, z)):
                    verts.append( (x, y, z) )
                    verts.append( (x, y+1, z) )
                    verts.append( (x, y+1, z+1) )
                    verts.append( (x, y, z+1) )
                    
                    faces.append( [len(verts)-4,
                                    len(verts)-3,
                                    len(verts)-2,
                                    len(verts)-1] )
                
                if not self.compareVox(colID, Vec3(x, y-1, z)):
                    verts.append( (x, y, z) )
                    verts.append( (x, y, z+1) )
                    verts.append( (x+1, y, z+1) )
                    verts.append( (x+1, y, z) )
                    
                    faces.append( [len(verts)-4,
                                    len(verts)-3,
                                    len(verts)-2,
                                    len(verts)-1] )
                
                if not self.compareVox(colID, Vec3(x, y, z-1)):
                    verts.append( (x, y, z) )
                    verts.append( (x+1, y, z) )
                    verts.append( (x+1, y+1, z) )
                    verts.append( (x, y+1, z) )
                    
                    faces.append( [len(verts)-4,
                                    len(verts)-3,
                                    len(verts)-2,
                                    len(verts)-1] )
                                        
            mesh.from_pydata(verts, [], faces)
            
            # Add materials
            if ImportVox.VMaterial == "NoMatNeeded" or ImportVox.VMaterial == None: pass
            else: obj.data.materials.append(ImportVox.VMaterial)

            
            # Create Vertex Colors & add data
            bpy.context.view_layer.objects.active = obj

            # Add color attributes for all selected maps, and also make variables for em
            if mytool.ImportColor:
                bpy.ops.geometry.color_attribute_add(name = "Color", domain='CORNER', data_type='BYTE_COLOR')
                ColorLayer = mesh.color_attributes["Color"]
                i = 0
                for poly in mesh.polygons:
                    for idx in poly.loop_indices:
                        ColorLayer.data[i].color = palette[Col-1]
                        i+=1 

            if mytool.ImportRoughness:
                bpy.ops.geometry.color_attribute_add(name = "Roughness", domain='CORNER', data_type='BYTE_COLOR')
                RoughnessLayer = mesh.color_attributes["Roughness"]
                i = 0
                for poly in mesh.polygons:
                    for idx in poly.loop_indices:
                        RoughnessLayer.data[i].color = [materials[Col-1][0], materials[Col-1][0], materials[Col-1][0], 1]
                        i+=1 

            if mytool.ImportMetallic:
                bpy.ops.geometry.color_attribute_add(name = "Metallic", domain='CORNER', data_type='BYTE_COLOR')
                MetallicLayer = mesh.color_attributes["Metallic"]
                i = 0
                for poly in mesh.polygons:
                    for idx in poly.loop_indices:
                        MetallicLayer.data[i].color = [materials[Col-1][1], materials[Col-1][1], materials[Col-1][1], 1]
                        i+=1 

            if mytool.ImportEmission:
                bpy.ops.geometry.color_attribute_add(name = "Emission", domain='CORNER', data_type='BYTE_COLOR')
                EmissionLayer = mesh.color_attributes["Emission"]
                i = 0
                for poly in mesh.polygons:
                    for idx in poly.loop_indices:
                        EmissionLayer.data[i].color = [materials[Col-1][2], materials[Col-1][2], materials[Col-1][2], 1]
                        i+=1 

            if mytool.ImportTransmission:
                bpy.ops.geometry.color_attribute_add(name = "Transmission", domain='CORNER', data_type='BYTE_COLOR')
                TransmissionLayer = mesh.color_attributes["Transmission"]
                i = 0
                for poly in mesh.polygons:
                    for idx in poly.loop_indices:
                        TransmissionLayer.data[i].color = [materials[Col-1][3], materials[Col-1][3], materials[Col-1][3], 1]
                        i+=1
            '''
            if mytool.ImportSubSurface:
                bpy.ops.geometry.color_attribute_add(name = "SubSurface", domain='CORNER', data_type='BYTE_COLOR')
                SSSLayer = mesh.color_attributes["SubSurface"]
                i = 0
                for poly in mesh.polygons:
                    for idx in poly.loop_indices:
                        SSSLayer.data[i].color = [materials[Col-1][4], materials[Col-1][4], materials[Col-1][4], 1]
                        i+=1
'''
            

        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select_set(True) # Select all objects that were generated.
        
        obj = objects[0]
        bpy.context.view_layer.objects.active = obj # Make the first one active.
        bpy.ops.object.join() # Join selected objects.
        
        # Sets the origin of object to be the same as in MagicaVoxel so that its location can be set correctly.
        bpy.context.scene.cursor.location = [0, 0, 0]
        obj.location = [int(-self.size.x/2), int(-self.size.y/2), int(-self.size.z/2)]
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        
        # Set scale, position & rotation.

        # Rescale value
        RescaleValue = 0.1

        TransformMatrix4x4[0][3] = TransformMatrix4x4[0][3]*RescaleValue
        TransformMatrix4x4[1][3] = TransformMatrix4x4[1][3]*RescaleValue
        TransformMatrix4x4[2][3] = TransformMatrix4x4[2][3]*RescaleValue
        
        obj.matrix_world = TransformMatrix4x4

        bpy.ops.transform.resize(value=(RescaleValue, RescaleValue, RescaleValue))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        

        # Remove Doubles & fix normals
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode = 'OBJECT')

        #Origin to Bottom, if specified
        if mytool.OriginsAtBottom:
            
            def Find_Min_Max_Verts(obj):
                bpy.ops.mesh.reveal()
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                
                if len(bm.verts) == 0: result = None
                else:
                    min_co = (obj.matrix_world @ bm.verts[0].co)[2]
                    for v in bm.verts:
                        if (obj.matrix_world @ v.co)[2] < min_co:
                            min_co = (obj.matrix_world @ v.co)[2]
                return min_co	

            # Save selected objects and current position of 3D Cursor
            SelectedObjs = bpy.context.selected_objects
            ActiveObj = bpy.context.active_object
            CursorLoc = bpy.context.scene.cursor.location.copy()

            bpy.ops.object.mode_set(mode = 'OBJECT')

            # Set origins to bottom
            for Obj in SelectedObjs:
                # Select only current object (for setting origin)
                bpy.ops.object.select_all(action='DESELECT')
                Obj.select_set(True);
                bpy.context.view_layer.objects.active = Obj
                # Save current origin and relocate 3D Cursor
                OriginLoc = Obj.location.copy() 
                if Obj.type == 'MESH':
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    min_co = Find_Min_Max_Verts(Obj)
                    if min_co == None:
                        min_co = OriginLoc[2]
                    
                    bpy.ops.object.mode_set(mode = 'OBJECT')
                    bpy.context.scene.cursor.location = [OriginLoc[0], OriginLoc[1], min_co]
                    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                    
                    # Reset 3D Cursor  
                    bpy.context.scene.cursor.location = CursorLoc
                    
            # Select objects again
            for Obj in SelectedObjs:
                Obj.select_set(True);
                
            bpy.context.view_layer.objects.active = ActiveObj


class ImportVox(Operator, ImportHelper):
    
    """Import a VOX file with the selected settings"""
    bl_idname = "voxcleaner.importvox"
    bl_label = "Import Vox Files"
    bl_options = {'UNDO'}

    MaterialName = None
    VMaterial = None

    files: CollectionProperty(name="File Path", description="File path used for importing the VOX file", type=bpy.types.OperatorFileListElement) # type: ignore

    directory: StringProperty() # type: ignore
    
    filename_ext = ".vox"
    filter_glob: StringProperty(default="*.vox",options={'HIDDEN'},) # type: ignore
    

    def execute(self, context):
        paths = [os.path.join(self.directory, name.name) for name in self.files]
        #print("Firstline whtvr",paths)

        if not paths:
            paths.append(self.filepath)
            print("SELF.fp",paths)
        
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Enter Object Mode before importing')
            return {'CANCELLED'}
        if batch.ACTIVE or FlowData.ProcessRunning:
            self.report({'WARNING'}, 'Finish the current clean operation first')
            return {'CANCELLED'}
        mytool = context.scene.vox_tool
        imported, failures = [], []
        cursor = context.scene.cursor.location.copy()
        for path in paths:
            before = set(bpy.data.objects)
            try:
                data = read_vox(path, StaticData.RoughnessDefault, mytool.MaxMaps)
                name = os.path.splitext(os.path.basename(path))[0]
                channels = (mytool.ImportColor, mytool.ImportRoughness,
                            mytool.ImportMetallic, mytool.ImportEmission, mytool.ImportTransmission)
                ImportVox.VMaterial = VoxMethods.CreateCRMETS(context, *channels) if any(channels) else "NoMatNeeded"
                collection = None
                if mytool.Organize:
                    collection = bpy.data.collections.new(name)
                    context.scene.collection.children.link(collection)
                for index, (model_id, model_name, visible, transform) in enumerate(data['instances']):
                    if not visible and not mytool.ImportHidden:
                        continue
                    size, voxels = data['models'][model_id]
                    model = VoxelObject(voxels, Vec3(*size))
                    model.generate(model_name or f'{name}_{index + 1}', data['palette'],
                                   data['materials'], collection, Matrix(transform))
                imported.extend(obj for obj in bpy.data.objects if obj not in before)
            except (OSError, ValueError, RuntimeError) as error:
                failures.append(f'{os.path.basename(path)}: {error}')
                for obj in set(bpy.data.objects) - before:
                    bpy.data.objects.remove(obj, do_unlink=True)
            finally:
                context.scene.cursor.location = cursor
                ImportVox.VMaterial = None
        bpy.ops.object.select_all(action='DESELECT')
        for obj in imported:
            obj.select_set(True)
        if imported:
            context.view_layer.objects.active = imported[0]
        message = f'Imported {len(imported)} models from {len(paths) - len(failures)}/{len(paths)} VOX files'
        if failures:
            message += '; ' + '; '.join(failures)
        self.report({'WARNING'} if failures else {'INFO'}, message)
        return {'FINISHED'} if imported else {'CANCELLED'}

    def draw(self, context):
        mytool = bpy.context.scene.vox_tool
        
        layout = self.layout

        # Import Maps
        BracketText = ""
        if mytool.ImportColor: BracketText+="C"
        if mytool.ImportRoughness: BracketText+="R"
        if mytool.ImportMetallic: BracketText+="M"
        if mytool.ImportEmission: BracketText+="E"
        if mytool.ImportTransmission: BracketText+="T"
        
        if BracketText == "CRMET": BracketText = "All"
        if BracketText == "": BracketText = "None"


        row = layout.row()
        row.label(icon='NODE_COMPOSITING',text = str("Map Imports (" + BracketText + ")"))
        row = layout.row()
        boks = row.box()
        row = boks.row()
        col = row.column(align = True)
        col.prop(mytool, "ImportColor")
        col.prop(mytool, "ImportRoughness")
        col.prop(mytool, "ImportMetallic")

        # Spacing
        row = col.row()      
        row.label(text = "   ")               
        row.scale_y = StaticData.SeperatorSpacing2

        col.prop(mytool, "ImportEmission")
        col.prop(mytool, "ImportTransmission")
        
        # Spacing
        row = layout.row()      
        row.label(text = "   ")               
        row.scale_y = StaticData.SeperatorSpacing1

        # Import Options
        row = layout.row()
        row.label(icon='OPTIONS',text = "Import Options")
        row = layout.row()
        boks = row.box()
        row = boks.row()
        col = row.column(align = True)
        col.prop(mytool, "ImportHidden")
        col.prop(mytool, "OriginsAtBottom")
        col.prop(mytool, "Organize")
        col.prop(mytool, "MaxMaps")

class VoxMethods():        

    def MrChecker(context):
        #Checks whether the selected 'things' are cleanable and exportable. Realtime.
        #Outputs in the form of CleaningStatus, StepStatus, ExportStatus
        mytool = context.scene.vox_tool

        if batch.ACTIVE:
            message = "Batch running; Esc to cancel"
            return message, message, message

        # Check for object mode
        if bpy.context.mode == 'OBJECT': pass
        else: return "Enter object mode to clean","Enter object mode to clean","Enter object mode for exports"

        # Check for 2 step process running
        if FlowData.ProcessRunning == False: pass
        else: return "2 Step Process is running. Finish that first.", 1, "2 Step Process is running. Finish that first."

        # No object selected
        if len(bpy.context.selected_objects) == 0: return "Please select an object","Please select an object","Please select an object"

        # multiple objects selected
        #if len(bpy.context.selected_objects) > 1: return "Please select a single object","Please select a single object","Please select a single object"

        # active Object not in selected
        if bpy.context.active_object not in bpy.context.selected_objects:
            if len(bpy.context.selected_objects) == 1: k = "Select the object properly"
            else: k = "Select the objects properly"
            return k, k, k
        
        # Mesh Check
        NonMeshPresent = False
        for object in bpy.context.selected_objects:
            if object.type != 'MESH':
                NonMeshPresent = True 
                break
        if NonMeshPresent:
            if len(bpy.context.selected_objects) == 1: k = "Select object of type MESH"
            else: k = "Not all selected objects are MESHES"
            return k, k, k


        # Clean or Bake Check for Lazy Clean
        if len(bpy.context.selected_objects) > 1: Lazy = "Please select a single object"

        SharedStatus = len(bpy.context.selected_objects)
        Lazy = SharedStatus if mytool.CleanGeo or mytool.BakeTex else "Select atleast one options above to clean"
        
        # Common UV Check for 2Step
        if len(bpy.context.selected_objects) == 1:TwoStep = 1
        else:
            if mytool.CommonUV:TwoStep = len(bpy.context.selected_objects)
            else:TwoStep = "Select a single object or Enable Shared UVs"

        return Lazy, TwoStep, len(bpy.context.selected_objects)
        
        
    def MrModelTypeChecker(ObjectList):
        #Checks and returns the model type for solo and list of models. Removes doubles and fixes normals in the process too! Not realtime.

        if len(ObjectList)>0:
            ActiveObj = bpy.context.active_object
            TypeList = set()
            FlowData.VertexCountInitialX = 0

            for obj in ObjectList:
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.view_layer.objects.active = None

                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                
                FlowData.VertexCountInitialX += len(obj.data.vertices)

                bpy.ops.object.mode_set(mode = 'EDIT')

                #Change color att domain, merge verts, Fix normals
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.object.mode_set(mode = 'OBJECT')

                # Blender 5.2 clears the active attribute when leaving Edit Mode.
                # Restore the active color attribute before using the context-sensitive
                # Attribute Convert operator. Meshes without a color attribute do not
                # need this conversion and should continue through the cleanup flow.
                ActiveColor = obj.data.color_attributes.active_color
                if ActiveColor is None and len(obj.data.color_attributes) > 0:
                    ActiveColor = obj.data.color_attributes[0]

                if ActiveColor is not None:
                    ActiveAttributeIndex = obj.data.attributes.find(ActiveColor.name)
                    if ActiveAttributeIndex >= 0:
                        obj.data.attributes.active_index = ActiveAttributeIndex
                        if (ActiveColor.domain != 'CORNER' or
                                ActiveColor.data_type != 'FLOAT_COLOR'):
                            if bpy.ops.geometry.attribute_convert.poll():
                                bpy.ops.geometry.attribute_convert(
                                    domain='CORNER', data_type='FLOAT_COLOR')
                bpy.ops.object.mode_set(mode = 'EDIT')

                bpy.ops.mesh.remove_doubles()
                bpy.ops.mesh.normals_make_consistent(inside=False)

                #Find ModelType
                bm = bmesh.from_edit_mesh(bpy.context.active_object.data)

                Type = "Voxel"
                try:
                    for e in bm.edges:
                        EdgeAngle = round(math.degrees(e.calc_face_angle()),3)
                        
                        if -0.02 < EdgeAngle <= 0.02 or 89 < EdgeAngle < 91:
                            continue
                        elif 44 < EdgeAngle < 46.0 or 0 < EdgeAngle < 1 or 34 < EdgeAngle < 36 or 53 < EdgeAngle < 55 or 70 < EdgeAngle < 71:
                            Type = "MC"
                        else:
                            Type = "Non Voxel"
                            print(EdgeAngle, end = "   ")
                            break 
                except ValueError:
                    pass
                bmesh.update_edit_mesh(bpy.context.active_object.data)

                TypeList.add(Type)            
                bpy.ops.object.mode_set(mode = 'OBJECT')

                # Fix Shading
                if Type in {"Voxel", "MC"}:
                    bpy.ops.object.shade_flat()


                if len(TypeList) > 1:
                    #select all selected objects & set the active object
                    bpy.context.view_layer.objects.active = ActiveObj
                    for obj in ObjectList:
                        obj.select_set(True)
                    return "Mixed"
                
            #select all selected objects & set the active object
            bpy.context.view_layer.objects.active = ActiveObj
            for obj in ObjectList:
                obj.select_set(True)
            return list(TypeList)[0]
    
    def ExportSummaries(context):
        #Gives out a summary of what I'm about to export along with the number of textures.

        scene = context.scene
        mytool = scene.vox_tool
        CleanStatus,StepStatus, ExportStatus = VoxMethods.MrChecker(context)

        if type(ExportStatus) == int:
            NoOfTextures = len(VoxMethods.GetTextures(context))

            ExportableMeshes = str(ExportStatus) + " Mesh" if ExportStatus == 1 else str(ExportStatus) + " Meshes"
            ExportableTextures = str(NoOfTextures) + " Texture" if NoOfTextures == 1 else str(NoOfTextures) + " Textures"
            stmt = "Export "+str(ExportableMeshes)+" with "+str(ExportableTextures)
            return stmt
        else:
            return "No Summary"
    

    def NextNamePlease(name):
        if name.rfind("_Backup") != -1:
            trail = name[name.rfind("_Backup")+7:]
            if trail == "":
                name = name[:name.rfind("_Backup")+7]+"2"
                return name
            else:
                if trail.isnumeric():
                    trail = str(int(trail)+1)
                    name = name[:name.rfind("_Backup")+7]+trail
                    return name
                else:
                    name = name + "_Backup"
                    return name
        else:
            name = name + "_Backup"
            return name

    def TriangulateModel(context):
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.mesh.quads_convert_to_tris()
        bpy.ops.object.mode_set(mode = 'OBJECT')

    def CreateCRMETS(context,C,R,M,E,T):
        mytool = bpy.context.scene.vox_tool

        # calculate the name for the CRMET material
        MaterialName = "VCMat"
        Suffix1 = "_"

        if any([C,R,M,E,T]) == False:Suffix1 += "0"
        else:
            if C:Suffix1+="C"
            if R:Suffix1+="R"
            if M:Suffix1+="M"
            if E:Suffix1+="E"
            if T:Suffix1+="T"

        MaterialName+=Suffix1
        print(MaterialName)
        print("No mat" if bpy.data.materials.get(MaterialName) is None else "Mat")
        # check material's availability
        if bpy.data.materials.get(MaterialName) is None:
            # Create New VMat, the one of this kind isn't there
            VMaterial = bpy.data.materials.new(name = MaterialName)

            VMaterial.use_nodes = True
            nodes = VMaterial.node_tree.nodes
            links = VMaterial.node_tree.links
            
            bsdf = nodes["Principled BSDF"]
            bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.5
            bsdf.inputs['Metallic'].default_value = 0.0
            bsdf.inputs['Emission Strength'].default_value = 0.0
            bsdf.inputs['Transmission Weight'].default_value = 0.0

            # Create and hookup nodes if the parameters say so 
            if C:
                ColAtt_Color = nodes.new("ShaderNodeVertexColor")
                ColAtt_Color.layer_name = "Color"
                ColAtt_Color.name = "Color"
                ColAtt_Color.location = (-324,466)

                links.new(ColAtt_Color.outputs["Color"], bsdf.inputs["Base Color"])

            if M:
                ColAtt_Metallic = nodes.new("ShaderNodeVertexColor")
                ColAtt_Metallic.layer_name = "Metallic"
                ColAtt_Metallic.name = "Metallic"
                ColAtt_Metallic.location = (-324,352)

                links.new(ColAtt_Metallic.outputs["Color"], bsdf.inputs["Metallic"])

            if R:
                ColAtt_Roughness = nodes.new("ShaderNodeVertexColor")
                ColAtt_Roughness.layer_name = "Roughness"
                ColAtt_Roughness.name = "Roughness"
                ColAtt_Roughness.location = (-324,238)

                links.new(ColAtt_Roughness.outputs["Color"], bsdf.inputs["Roughness"])

            if T:
                ColAtt_Transmission = nodes.new("ShaderNodeVertexColor")
                ColAtt_Transmission.layer_name = "Transmission"
                ColAtt_Transmission.name = "Transmission"
                ColAtt_Transmission.location = (-324,10)

                links.new(ColAtt_Transmission.outputs["Color"], bsdf.inputs["Transmission Weight"])

            if E:
                ColAtt_Emission = nodes.new("ShaderNodeVertexColor")
                ColAtt_Emission.layer_name = "Emission"
                ColAtt_Emission.name = "Emission"
                ColAtt_Emission.location = (-324,-104)

                links.new(ColAtt_Emission.outputs["Color"], bsdf.inputs["Emission Strength"])
                if C:
                    links.new(ColAtt_Color.outputs["Color"], bsdf.inputs["Emission Color"])
        else: 
            # if the material is already there
            VMaterial = bpy.data.materials.get(MaterialName)
        
        return VMaterial


    def JoinModels(context):
        bpy.ops.object.mode_set(mode = 'OBJECT')
        ObjArray = bpy.context.selected_objects
        ObjActive = bpy.context.view_layer.objects.active
        
        OG3DCursorPos = [round(bpy.context.scene.cursor.location.x,2),round(bpy.context.scene.cursor.location.y,2),round(bpy.context.scene.cursor.location.z,2)]

        # Run the loop of making vertex groups & Storing OriginPositionData
        for Obj in ObjArray:
            bpy.ops.object.select_all(action='DESELECT')
            Obj.select_set(True)
            bpy.context.view_layer.objects.active = Obj
            
            bpy.ops.object.mode_set(mode = 'EDIT')
            
            Obj.vertex_groups.new(name = Obj.name)
            
            # assiggn the whole object in there
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.object.vertex_group_assign()
            bpy.ops.object.mode_set(mode = 'OBJECT')

            #Set the cursor to the obj origin, store the location
            FlowData.CommonUVOrigins[str(Obj.name)] = [round(Obj.location.x,2),round(Obj.location.y,2),round(Obj.location.z,2)]

        bpy.context.scene.cursor.location = OG3DCursorPos

        
        #before joining, add VCMat_0 on objects that dont have any material
        for obj in ObjArray:
            if obj.type == 'MESH':
                if len(obj.data.materials) == 0:
                    # No material slots
                    obj.data.materials.append(VoxMethods.CreateCRMETS(context,False,False,False,False,False))
                else:
                    # check for empty mat slots - if present, kill em
                    VoxMethods.ClearEmptyMaterialSlots(obj)
        
        # join all them objects
        bpy.ops.object.select_all(action='DESELECT')
        for Obj in ObjArray:
            Obj.select_set(True)
        bpy.context.view_layer.objects.active = ObjActive
        
        bpy.ops.object.join()
        
        # Rename as The Set 
        bpy.context.view_layer.objects.active.name = ObjActive.name+"Set"


    def SplitModels(context,):
        # Set the active object to the one you want to work with
        obj = bpy.context.active_object

        # Ensure the object is in object mode
        #bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='OBJECT')

        # Get the vertex groups
        vertex_groups = obj.vertex_groups

        OG3DCursorPos2 = [round(bpy.context.scene.cursor.location.x,2),round(bpy.context.scene.cursor.location.y,2),round(bpy.context.scene.cursor.location.z,2)]

        # Iterate through all vertex groups
        SplitUpModels = []
        for Vgroup in vertex_groups:
            VertGrupName = Vgroup.name
            
            # Create a new object by duplicating the original object
            new_obj = obj.copy()
            new_obj.data = obj.data.copy()
            bpy.context.collection.objects.link(new_obj)
            
            # Select the geo first based on the Vgroups
            bpy.ops.object.select_all(action='DESELECT')
            new_obj.select_set(True)
            bpy.context.view_layer.objects.active = new_obj

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.vertex_group_set_active(group=VertGrupName)
            bpy.ops.object.vertex_group_select()

            # delete the unnecessary geo 
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.delete(type='VERT')
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Clear out all vertex groups in the new obj
            for v_group in new_obj.vertex_groups:
                new_obj.vertex_groups.remove(v_group)

            # set the cursor location to the dict vector
            bpy.context.scene.cursor.location = FlowData.CommonUVOrigins[str(Vgroup.name)]
            # set the origin loation to the cursor location
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')


            # remove VCMat_0 if present on the model
            if len(new_obj.data.materials) > 0:
                # check for emptyVCMat_0 mat slots - if present, kill em
                for slot in new_obj.material_slots:
                    if slot.name == "VCMat_0": new_obj.data.materials.pop(index = slot.slot_index)
            
            # Rename the new object with the vertex group name
            new_obj.name = VertGrupName
            SplitUpModels.append(new_obj)

        bpy.context.scene.cursor.location = OG3DCursorPos2

        # Delete the OG Obj
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.delete(use_global=False)

        return SplitUpModels
    
    def ApplySplitToBothObjects(context):
        scene = context.scene
        mytool = scene.vox_tool
        #If no backup, just add the dupe to the global list
        if mytool.CreateBackup == False: FlowData.CommonUVDupeObjects = [FlowData.DupeObj]
        else:
            # make the dupe active & visible
            FlowData.DupeObj.hide_set(False)
            bpy.ops.object.select_all(action='DESELECT')
            FlowData.DupeObj.select_set(True)
            bpy.context.view_layer.objects.active = FlowData.DupeObj
            
            # split & rename dupes & add it to the global dupes list
            ObjectsToBeRenamed = VoxMethods.SplitModels(context)
            for obj in ObjectsToBeRenamed: obj.name = VoxMethods.NextNamePlease(obj.name)

            FlowData.CommonUVDupeObjects = ObjectsToBeRenamed
            
        # split the main models as well
        bpy.ops.object.select_all(action='DESELECT')
        FlowData.MainObj.select_set(True)
        bpy.context.view_layer.objects.active = FlowData.MainObj
        VoxMethods.SplitModels(Context)

    def ClearEmptyMaterialSlots(objekt):
        if len(objekt.material_slots) == 1:
            if objekt.material_slots[0].name == "": objekt.data.materials.clear()
        else:
            i = 0
            while i<len(objekt.material_slots):
                if objekt.material_slots[i].name == "":
                    objekt.data.materials.pop(index = i)
                else:
                    i+= 1

        # if all were emptied, There wll remain a single empty one. Get rid of it.
        if len(objekt.material_slots) == 1:
            if objekt.material_slots[0].name == "": objekt.data.materials.clear()


    def ModelFixing(context):
        
        FlowData.ProcessRunning = True
        
        # set main object and its name
        FlowData.MainObj = bpy.context.active_object
        FlowData.MainObjName = bpy.context.active_object.name
        FlowData.MainObj.hide_render = False

        for ColAtt in FlowData.MainObj.data.color_attributes:
            FlowData.MaterialMaps.append(ColAtt.name)

        # Clear empty material slots
        VoxMethods.ClearEmptyMaterialSlots(FlowData.MainObj)
        
        # duplicate the main obj, set and name dupe
        bpy.ops.object.duplicate()
        FlowData.DupeObj = bpy.context.active_object

        #Backup Name calculation
        FlowData.DupeObj.name = VoxMethods.NextNamePlease(FlowData.MainObjName)
        FlowData.DupeObjName = FlowData.DupeObj.name

        #Hide Dupe obj
        FlowData.DupeObj.hide_set(True)

        bpy.ops.object.select_all(action='DESELECT')

        # Remove color attributes from the main
        while FlowData.MainObj.data.color_attributes: FlowData.MainObj.data.color_attributes.remove(FlowData.MainObj.data.color_attributes[0])
        

        FlowData.MainObj.select_set(True)
        bpy.context.view_layer.objects.active = FlowData.MainObj

    def MaterialSetUp(context):
        
        scene = context.scene
        mytool = scene.vox_tool

        # analyse the current material on MainObj. make a bakelist based on the colAtt nodes present
        for mat in FlowData.MainObj.data.materials:
            if mat is None: continue
            else:  mat.use_nodes = True

            for node in mat.node_tree.nodes:
                if node.type == 'VERTEX_COLOR' and node.mute == False:
                    if node.layer_name != None:
                        if node.layer_name == "Color" or node.layer_name == "Col":
                            FlowData.BakeList.append("Color")
                        if node.layer_name == "Roughness":
                            FlowData.BakeList.append("Roughness")
                        if node.layer_name == "Metallic":
                            FlowData.BakeList.append("Metallic")
                        if node.layer_name == "Emission":
                            FlowData.BakeList.append("Emission")
                        if node.layer_name == "Transmission":
                            FlowData.BakeList.append("Transmission")

        FlowData.BakeList.append("Color")   # Color should always be present)
        FlowData.BakeList = list(set(FlowData.BakeList))
                        
                        

        # remove then add a new material
        FlowData.MainObj.data.materials.clear()

        ImageMaterial = bpy.data.materials.new(name = FlowData.MainObj.name + "_Material")
        #bpy.ops.object.material_slot_add()

        FlowData.MainObj.data.materials.append(ImageMaterial)

        # edit the material
        ImageMaterial.use_nodes = True
        nodes = ImageMaterial.node_tree.nodes

        #PrincipledBSDF
        PrincipledBSDF = nodes.get('Principled BSDF')
        PrincipledBSDF.location = (370,195)

        # MaterialOutput
        MO = nodes.get('Material Output')
        MO.location = (680,220)

        # All the Image Texture Nodes & their links
        Links = ImageMaterial.node_tree.links
        
        #print("MaterialMaps ",FlowData.MaterialMaps)
        #print("BakeList ",FlowData.BakeList)

        # Make image tex nodes for every map in Bakelist
        for Map in FlowData.BakeList:
            if Map == "Color":
                ImageTextureNode = nodes.new(type = 'ShaderNodeTexImage')
                ImageTextureNode.name = "Color"
                ImageTextureNode.interpolation = 'Closest' if FlowData.ModelType == "Voxel" else 'Linear'
                ImageTextureNode.location = (-434,695)

                Links.new(ImageTextureNode.outputs[0], PrincipledBSDF.inputs["Base Color"])

                Links.new(ImageTextureNode.outputs[0], PrincipledBSDF.inputs['Emission Color'])

            if Map == "Roughness":
                ImageTextureNode = nodes.new(type = 'ShaderNodeTexImage')
                ImageTextureNode.name = "Roughness"
                ImageTextureNode.interpolation = 'Closest'
                ImageTextureNode.location = (-434,143)

                Links.new(ImageTextureNode.outputs[0], PrincipledBSDF.inputs["Roughness"])

            if Map == "Metallic":
                ImageTextureNode = nodes.new(type = 'ShaderNodeTexImage')
                ImageTextureNode.name = "Metallic"
                ImageTextureNode.interpolation = 'Closest'
                ImageTextureNode.location = (-434,419)

                Links.new(ImageTextureNode.outputs[0], PrincipledBSDF.inputs["Metallic"])

            if Map == "Emission":
                ImageTextureNode = nodes.new(type = 'ShaderNodeTexImage')
                ImageTextureNode.name = "Emission"
                ImageTextureNode.interpolation = 'Closest'
                ImageTextureNode.location = (-115,-496)

                MathNode = nodes.new(type = 'ShaderNodeMath')
                MathNode.name = "EmissionMultiplier"
                MathNode.label = "Emission Strength"
                MathNode.operation = 'MULTIPLY'
                MathNode.location = (144,-496)

                Links.new(ImageTextureNode.outputs[0], MathNode.inputs[0])
                Links.new(MathNode.outputs[0], PrincipledBSDF.inputs["Emission Strength"])

                MathNode.inputs[1].default_value = mytool.EmitStrength
            
            if Map == "Transmission":
                ImageTextureNode = nodes.new(type = 'ShaderNodeTexImage')
                ImageTextureNode.name = "Transmission"
                ImageTextureNode.interpolation = 'Closest'
                ImageTextureNode.location = (-115,-220)

                Links.new(ImageTextureNode.outputs[0], PrincipledBSDF.inputs["Transmission Weight"])
            



        #l3 = Links.new(ImageTextureNode.outputs[0], MixRGB.inputs[1])
        l4 = Links.new(PrincipledBSDF.outputs[0], MO.inputs[0])
        
        # Link Set Default emit strength at the start

            
    def UVProjection(context):

        scene = context.scene
        mytool = scene.vox_tool
        
        bpy.ops.object.select_all(action='DESELECT')
        
        FlowData.MainObj.select_set(True)
        bpy.context.view_layer.objects.active = FlowData.MainObj

        #remove the base material on main if no bake texture is going on
        if FlowData.CleanType == "Lazy" and mytool.BakeTex == False:
            FlowData.MainObj.data.materials.clear()
        
        # Project UVs based on the selected Method
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        if FlowData.ModelType == "Voxel" and mytool.UVMethod == "smart": 
            bpy.ops.uv.smart_project(margin_method='SCALED', island_margin=0)
        else:bpy.ops.uv.cube_project(cube_size=1)


        bpy.ops.uv.select_all(action='SELECT')

        if FlowData.ModelType == "Voxel": bpy.ops.uv.pack_islands(rotate=mytool.RotateUV,scale = True, rotate_method='CARDINAL', margin=0, shape_method='CONVEX')
        elif FlowData.ModelType == "MC": bpy.ops.uv.pack_islands(rotate=True,rotate_method='CARDINAL',scale = True, margin=1/128, shape_method='CONCAVE')
        else: bpy.ops.uv.pack_islands(rotate=True, rotate_method='ANY', scale = True, margin=1/128, shape_method='CONCAVE')

        bpy.ops.object.mode_set(mode = 'OBJECT')

        # Decide texture size for different model
        if FlowData.ModelType == "Voxel":

            bpy.ops.object.mode_set(mode = 'EDIT')

            ob = FlowData.MainObj
            bm = bmesh.from_edit_mesh(ob.data)


            bpy.ops.mesh.select_all(action='DESELECT')

            FlowData.SmallestEdge = None
            FlowData.SmallestEdgeLength = 1000000000000.0

            for e in bm.edges:
                if e.calc_length() < FlowData.SmallestEdgeLength:
                    bpy.ops.mesh.select_all(action='DESELECT')
                    FlowData.SmallestEdgeLength = e.calc_length()
                    e.select = True
                    FlowData.SmallestEdge = e

            uv_layer = bm.loops.layers.uv.active

            a = FlowData.SmallestEdge.link_loops[0][uv_layer].uv
            b = FlowData.SmallestEdge.link_loops[0].link_loop_next[uv_layer].uv

            FractionDistance = math.dist(a, b)

            #print("Fractal Dist",FractionDistance)
            FlowData.ApproxLen = 1/FractionDistance
            bmesh.update_edit_mesh(bpy.context.active_object.data)

            bpy.ops.object.mode_set(mode = 'OBJECT')

            # Pick an image resolution
            if mytool.ResolutionSet == 'Stan':
                for resolution in StaticData.StandardBakeResolutions:
                    if FlowData.ApproxLen <= resolution:
                        FlowData.AutoRes = resolution
                        break
            else:
                FlowData.AutoRes = math.ceil(FlowData.ApproxLen)
            #print(FlowData.AutoRes)

            #Apply Multiplier to get the final result
            FlowData.FinalTextureSize = FlowData.AutoRes * int(mytool.TextureScaleMultiplier)
            bpy.ops.object.mode_set(mode = 'OBJECT')
        else:
            FlowData.FinalTextureSize = int(mytool.MCNVResolution)

        # Generate textures & assign them their nodes, if image baking is enabled
        if (FlowData.CleanType == "Lazy" and mytool.BakeTex == True) or (FlowData.CleanType == "2Step"):
            #print("UV Proj", FlowData.CleanType, mytool.BakeTex)
            for Map in FlowData.BakeList:
                if Map == "Color":
                    FlowData.GeneratedTex_Color = bpy.data.images.new(FlowData.MainObj.name + "_Color", int(FlowData.FinalTextureSize), int(FlowData.FinalTextureSize), alpha = mytool.AlphaBool)
                    bpy.data.images[FlowData.MainObj.name + "_Color"].generated_color = (mytool.BaseColor[0],mytool.BaseColor[1],mytool.BaseColor[2],mytool.BaseColor[3])
                    
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Color"].image = FlowData.GeneratedTex_Color

                if Map == "Roughness":
                    FlowData.GeneratedTex_Roughness = bpy.data.images.new(FlowData.MainObj.name + "_Roughness", int(FlowData.FinalTextureSize), int(FlowData.FinalTextureSize), alpha = False)
                    bpy.data.images[FlowData.MainObj.name + "_Roughness"].generated_color = (0,0,0,1)
                    
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Roughness"].image = FlowData.GeneratedTex_Roughness
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Roughness"].image.colorspace_settings.name = 'Non-Color'


                if Map == "Metallic":
                    FlowData.GeneratedTex_Metallic = bpy.data.images.new(FlowData.MainObj.name + "_Metallic", int(FlowData.FinalTextureSize), int(FlowData.FinalTextureSize), alpha = False)
                    bpy.data.images[FlowData.MainObj.name + "_Metallic"].generated_color = (0,0,0,1)
                    
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Metallic"].image = FlowData.GeneratedTex_Metallic
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Metallic"].image.colorspace_settings.name = 'Non-Color'

                if Map == "Emission":
                    FlowData.GeneratedTex_Emisson = bpy.data.images.new(FlowData.MainObj.name + "_Emission", int(FlowData.FinalTextureSize), int(FlowData.FinalTextureSize), alpha = False)
                    bpy.data.images[FlowData.MainObj.name + "_Emission"].generated_color = (0,0,0,1)
                    
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Emission"].image = FlowData.GeneratedTex_Emisson
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Emission"].image.colorspace_settings.name = 'Non-Color'
                
                if Map == "Transmission":
                    FlowData.GeneratedTex_Transmission = bpy.data.images.new(FlowData.MainObj.name + "_Transmission", int(FlowData.FinalTextureSize), int(FlowData.FinalTextureSize), alpha = False)
                    bpy.data.images[FlowData.MainObj.name + "_Transmission"].generated_color = (0,0,0,1)
                    
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Transmission"].image = FlowData.GeneratedTex_Transmission
                    FlowData.MainObj.data.materials[0].node_tree.nodes["Transmission"].image.colorspace_settings.name = 'Non-Color'


        #  Pick an active texture to be put up in the uv editor
            if FlowData.GeneratedTex_Color != None:
                FlowData.GeneratedTex_Active = FlowData.GeneratedTex_Color
            elif FlowData.GeneratedTex_Roughness != None:
                FlowData.GeneratedTex_Active = FlowData.GeneratedTex_Roughness
            elif FlowData.GeneratedTex_Metallic != None:
                FlowData.GeneratedTex_Active = FlowData.GeneratedTex_Metallic
            elif FlowData.GeneratedTex_Emisson != None:
                FlowData.GeneratedTex_Active = FlowData.GeneratedTex_Emisson
            elif FlowData.GeneratedTex_Transmission != None:
                FlowData.GeneratedTex_Active = FlowData.GeneratedTex_Transmission

        else:
            # No texture seems to be there
            print("lol no texture")
            pass

        #Set the active texture in the uv editor, if uv editor is available and is not being used by a Viewer Node.
        for Screen in bpy.data.screens:
            for area in Screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    if area.spaces.active.image != None and area.spaces.active.image.name == 'Viewer Node':
                        pass
                    else:
                        area.spaces.active.image = FlowData.GeneratedTex_Active

    def GeometryCleanUp(context):

        if FlowData.ModelType in {"Voxel", "MC"}:
            # Voxel/MC Model
            #Add and apply modifiers
            bpy.ops.object.mode_set(mode = 'OBJECT')
            FlowData.MainObj.modifiers.new("MrCleaner",'DECIMATE')
            FlowData.MainObj.modifiers["MrCleaner"].decimate_type = 'DISSOLVE'
            FlowData.MainObj.modifiers["MrCleaner"].delimit = {'SHARP'}
            FlowData.MainObj.data = FlowData.MainObj.data.copy()
            bpy.ops.object.modifier_apply(modifier="MrCleaner", report=True)

            # select main
            FlowData.MainObj.select_set(False)
            FlowData.DupeObj.select_set(False)
            bpy.context.view_layer.objects.active = FlowData.MainObj
            
            # Triangulate Dissolve Loop
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            
            i = 0
            while i<StaticData.TriangulateLoops:
                bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
                bpy.ops.mesh.dissolve_limited(angle_limit=0.0872665, delimit={'SHARP'}, use_dissolve_boundaries=False)
                i+=1
            
            bpy.ops.object.mode_set(mode = 'OBJECT')
        else:
            # Non-Voxel Model
            #Add and apply modifiers
            FlowData.MainObj.modifiers.new("MrCleaner",'DECIMATE')
            FlowData.MainObj.modifiers["MrCleaner"].decimate_type = 'COLLAPSE'
            if FlowData.VertexCountInitialX > 3000:
                DecimationRatio = 0.25
            else:
                DecimationRatio = 3000/FlowData.VertexCountInitialX

            bpy.context.object.modifiers["MrCleaner"].ratio = 1.0 - context.scene.vox_tool.NVDecimation / 100.0
            bpy.ops.object.modifier_apply(modifier="MrCleaner", report=True)

            # select main
            FlowData.MainObj.select_set(False)
            FlowData.DupeObj.select_set(False)
            bpy.context.view_layer.objects.active = FlowData.MainObj
           
        FlowData.VertexCountFinalX = len(FlowData.MainObj.data.vertices)

    def UVScaling(context):
        scene = context.scene
        mytool = scene.vox_tool
        #actually scale the UVs according to ScaleFactor n cursor location-------------------------------------can be done with lighter detail

        bpy.ops.object.mode_set(mode = 'EDIT')
        ob = FlowData.MainObj
        bm = bmesh.from_edit_mesh(ob.data)

        bpy.ops.mesh.select_all(action='DESELECT')

        #The NonDiagonal Function
        def NonDiagonal(v1,v2):
            if v1.x != v2.x:
                if v1.y != v2.y or v1.z != v2.z:
                    return False
                
            elif v1.y != v2.y:
                if v1.x != v2.x or v1.z != v2.z:
                    return False
                
            elif v1.z != v2.z:
                if v1.x != v2.x or v1.y != v2.y:
                    return False
            return True

        # Make a set of NonDiagonal edges
        NonDiagonalEdges = []
        for edge in bm.edges:
            v1,v2 = edge.verts
            v1co = v1.co
            v2co = v2.co
            if NonDiagonal(v1co,v2co):
                NonDiagonalEdges.append(edge)

        #Check the lengths in them if one is the longest
        bpy.ops.mesh.select_all(action='DESELECT')
        for le in NonDiagonalEdges:
            if le.calc_length() > FlowData.LargestEdgeLength:
                bpy.ops.mesh.select_all(action='DESELECT')
                FlowData.LargestEdgeLength = le.calc_length()
                le.select = True
                FlowData.LargestEdge = le

        FlowData.LargestEdgeBlocks = round(FlowData.LargestEdgeLength/FlowData.SmallestEdgeLength,0)

        uv_layer = bm.loops.layers.uv.active

        p = FlowData.LargestEdge.link_loops[0][uv_layer].uv*FlowData.AutoRes
        q = FlowData.LargestEdge.link_loops[0].link_loop_next[uv_layer].uv*FlowData.AutoRes

        FlowData.LargestUVEdgeLengthInPixels = math.dist(p, q)

        FlowData.ResizeFactor = FlowData.LargestEdgeBlocks/FlowData.LargestUVEdgeLengthInPixels
        
        bpy.ops.object.mode_set(mode = 'OBJECT')

        ob = FlowData.MainObj

        bpy.ops.object.mode_set(mode = 'EDIT')
        
        bpy.ops.uv.select_all(action='SELECT')
        bm = bmesh.from_edit_mesh(ob.data)
        uv_layer = bm.loops.layers.uv.verify()
        
        for Screen in bpy.data.screens:
            for area in Screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.cursor_location[0] = 0
                    area.spaces.active.cursor_location[1] = 0
                    area.spaces.active.pivot_point = 'CURSOR'
        
        for face in bm.faces:
            for loop in face.loops:
                loop_uv = loop[uv_layer]
                
                loop_uv.uv *= FlowData.ResizeFactor
        
        bmesh.update_edit_mesh(bpy.context.active_object.data)
        bpy.ops.object.mode_set(mode = 'OBJECT')


        
        # Snap UV boundaries to image pixels in foreground and background Blender.
        if FlowData.GeneratedTex_Active is not None:
            width, height = FlowData.GeneratedTex_Active.size
            for loop in FlowData.MainObj.data.uv_layers.active.data:
                loop.uv = (math.floor(loop.uv.x * width + 0.5) / width,
                           math.floor(loop.uv.y * height + 0.5) / height)

    def TextureBake(context):
        scene = context.scene
        engine = scene.render.engine
        device, bake_type = scene.cycles.device, scene.cycles.bake_type
        fields = ('use_pass_color', 'use_pass_direct', 'use_pass_indirect', 'use_clear',
                  'use_selected_to_active', 'cage_extrusion', 'max_ray_distance', 'margin', 'margin_type')
        saved = {key: getattr(scene.render.bake, key) for key in fields}
        source = FlowData.DupeObj
        original_materials = list(source.data.materials)
        copies = [mat.copy() if mat else None for mat in original_materials]
        source.data.materials.clear()
        for mat in copies:
            source.data.materials.append(mat)
        try:
            VoxMethods._TextureBake(context)
        finally:
            source.data.materials.clear()
            for mat in original_materials:
                source.data.materials.append(mat)
            for mat in copies:
                if mat is not None and mat.users == 0:
                    bpy.data.materials.remove(mat)
            for key, value in saved.items():
                setattr(scene.render.bake, key, value)
            scene.cycles.device, scene.cycles.bake_type = device, bake_type
            scene.render.engine = engine
            source.hide_set(True)

    def _TextureBake(context):

        #No material on Dupe - bake aise hi
        #Some random material on Dupe - bake diffuse aise hi
        #CRMET material on Dupe(detect using presence of image texture nodes) - bake all channels present 

        scene = context.scene
        mytool = scene.vox_tool

        # Copy Bake settings
        RenderEngine = bpy.context.scene.render.engine

        # set bake settings
        bpy.context.scene.render.engine = 'CYCLES'
        # Honor the scene device; batch workers explicitly use CPU.
        if scene.cycles.device == 'GPU':
            preferences = context.preferences.addons.get('cycles')
            if preferences is None or not preferences.preferences.has_active_device():
                scene.cycles.device = 'CPU'

        bpy.context.scene.cycles.bake_type = 'EMIT'
        bpy.context.scene.render.bake.use_pass_color = True
        bpy.context.scene.render.bake.use_pass_direct = False
        bpy.context.scene.render.bake.use_pass_indirect = False

        bpy.context.scene.render.bake.use_clear = False
        bpy.context.scene.render.bake.use_selected_to_active = True
        if FlowData.ModelType == "Voxel": bpy.context.scene.render.bake.cage_extrusion = 0.001
        else: bpy.context.scene.render.bake.cage_extrusion = 0.01
        bpy.context.scene.render.bake.max_ray_distance = 0.1
        
        if FlowData.ModelType == "Voxel":
            bpy.context.scene.render.bake.margin = 0      #margin
        else:
            bpy.context.scene.render.bake.margin = FlowData.Bleed = int(int(FlowData.FinalTextureSize)/128)     # Some calculated Bleed
            bpy.context.scene.render.bake.margin_type = 'EXTEND'

        # Unhide the Dupe object
        FlowData.DupeObj.hide_set(False)

        # Select objects in order
        bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        FlowData.MainObj.select_set(True)
        FlowData.DupeObj.select_set(True)
        bpy.context.view_layer.objects.active = FlowData.MainObj      

        # Get mainObj NodeTree
        FlowData.MainObj.material_slots[0].material.use_nodes = True
        NodeTree = FlowData.MainObj.material_slots[0].material.node_tree

        # 1. Copy
        # 2. Clean slate
        # 3. Bake
        # 4. Reset


        # Get DupeObj Material Stats
        if len(FlowData.DupeObj.data.materials) > 0:
            # Store all the color sources from all the dupe materials into a dictionary.
            SourceData = {}

            for mat in FlowData.DupeObj.data.materials:

                # 1. Copy values - copy the PBSDF values in a dict, that would be changing during the process
                mat.use_nodes = True

                MaterialInputs = mat.node_tree.nodes['Principled BSDF'].inputs
                SourceData[mat.name] = {}
                SourceData[mat.name]["Color"] = MaterialInputs['Base Color'].links[0].from_socket if len(MaterialInputs['Base Color'].links)>0 else [MaterialInputs['Base Color'].default_value[0],MaterialInputs['Base Color'].default_value[1],MaterialInputs['Base Color'].default_value[2],1]    # bpyNode or Vec4 
                SourceData[mat.name]["Roughness"] = MaterialInputs['Roughness'].links[0].from_socket if len(MaterialInputs['Roughness'].links)>0 else MaterialInputs['Roughness'].default_value      # bpyNode or float
                SourceData[mat.name]["Metallic"] = MaterialInputs['Metallic'].links[0].from_socket if len(MaterialInputs['Metallic'].links)>0 else MaterialInputs['Metallic'].default_value      # bpyNode or float
                SourceData[mat.name]["Emission"] = MaterialInputs['Emission Strength'].links[0].from_socket if len(MaterialInputs['Emission Strength'].links)>0 else MaterialInputs['Emission Strength'].default_value    # bpyNode or float
                SourceData[mat.name]["Transmission"] = MaterialInputs["Transmission Weight"].links[0].from_socket if len(MaterialInputs["Transmission Weight"].links)>0 else MaterialInputs["Transmission Weight"].default_value    # bpyNode or float


                # 2. Clean slate - Gotta remove things which are commected to the BSDF and will cause inaccuracies in bake. (for eg, weird roughness values(plugged in or an actual value) 
                #So, kill all the links and set the values to default from the StaticData values
                if len(MaterialInputs['Base Color'].links)>0:mat.node_tree.links.remove(MaterialInputs['Base Color'].links[0]) 
                MaterialInputs['Base Color'].default_value = (1.0,1.0,1.0,1.0)

                if len(MaterialInputs['Roughness'].links)>0:mat.node_tree.links.remove(MaterialInputs['Roughness'].links[0]) 
                MaterialInputs['Roughness'].default_value = 0.5

                if len(MaterialInputs['Metallic'].links)>0:mat.node_tree.links.remove(MaterialInputs['Metallic'].links[0]) 
                MaterialInputs['Metallic'].default_value = 0.0

                if len(MaterialInputs['Emission Strength'].links)>0:mat.node_tree.links.remove(MaterialInputs['Emission Strength'].links[0]) 
                MaterialInputs['Emission Strength'].default_value = 0.0

                if len(MaterialInputs['Transmission Weight'].links)>0:mat.node_tree.links.remove(MaterialInputs['Transmission Weight'].links[0]) 
                MaterialInputs['Transmission Weight'].default_value = 0.0
                
            #print("SourceData: ",SourceData) 
        else:
            print("No Materials on Dupe")
            

        def HandleBothTheMaterialsAndBake(Map):

            # Select the Image node in Main NodeTree
            for node in NodeTree.nodes:
                if node.name == Map:
                    node.select = True
                    NodeTree.nodes.active = node
                else:
                    node.select = False

            # Make a new link in all Dupe materials from whatever is connected in the source to PBSDF color
            for mat in FlowData.DupeObj.data.materials:
                Source = SourceData[mat.name][Map]
                PlugInHere = 0

                #remove whatever is connected first
                if len(mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].links)>0: mat.node_tree.links.remove(mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].links[0]) 

                if type(Source) == list:
                    mat.node_tree.nodes['Principled BSDF'].inputs[PlugInHere].default_value = Source
                elif type(Source) == float:
                    mat.node_tree.nodes['Principled BSDF'].inputs[PlugInHere].default_value[0] = Source
                    mat.node_tree.nodes['Principled BSDF'].inputs[PlugInHere].default_value[1] = Source
                    mat.node_tree.nodes['Principled BSDF'].inputs[PlugInHere].default_value[2] = Source
                    mat.node_tree.nodes['Principled BSDF'].inputs[PlugInHere].default_value[3] = 1
                else:                      #type(Source) == bpy.types.NodeSocketColor possibly some bpy node type like color, shader, float etc
                    try: mat.node_tree.links.new(Source, mat.node_tree.nodes['Principled BSDF'].inputs[PlugInHere])
                    except: pass
            
            # Diffuse Bake
            bpy.ops.object.bake(type='DIFFUSE')

        # 3. Bake - Baking all the maps using the function
        for Key in FlowData.BakeList:
            HandleBothTheMaterialsAndBake(Key)

        def LoadGivenDatainGivenMaterialMap(GivenData, DestinationMap):
            if type(SourceData[mat.name][GivenData]) == list : MatNodes['Principled BSDF'].inputs[DestinationMap].default_value = SourceData[mat.name][GivenData]    # Plug in a Vec4
            elif type(SourceData[mat.name][GivenData]) == float : MatNodes['Principled BSDF'].inputs[DestinationMap].default_value = SourceData[mat.name][GivenData]   # Plug in a float
            else:
                try: MatLinks.new(SourceData[mat.name][GivenData],  MatNodes['Principled BSDF'].inputs[DestinationMap])     # plug in a bpyNode
                except: pass
                
        # 4. Reset - Load all the data from the dictiomary, plug those values back in the diffuse channel. Do this for all materials
        for mat in FlowData.DupeObj.data.materials:
            MatLinks = mat.node_tree.links
            MatNodes = mat.node_tree.nodes

            LoadGivenDatainGivenMaterialMap("Color", "Base Color")
            LoadGivenDatainGivenMaterialMap("Roughness", "Roughness")
            LoadGivenDatainGivenMaterialMap("Metallic", "Metallic")
            LoadGivenDatainGivenMaterialMap("Emission", "Emission Strength")
            LoadGivenDatainGivenMaterialMap("Transmission", "Transmission Weight")

        #Pack the images for safety
        try:
            for Node in NodeTree.nodes:
                if Node.name in FlowData.BakeList:
                    Node.image.pack()
        except:
            pass

        # Hide the Dupe
        FlowData.DupeObj.hide_set(True)
        
        bpy.context.scene.render.engine = RenderEngine
        
    def EndProcess(context):

        scene = context.scene
        mytool = scene.vox_tool
        
        #clear existing VColor Data in the object if it exists
        try:
            if FlowData.MainObj.data.vertex_colors.active != None:
                FlowData.MainObj.data.vertex_colors.remove(FlowData.MainObj.data.vertex_colors.active)
        except Exception: 
            pass

        
        #Print Existing FlowData n MetaData
        if FlowData.ProcessRunning:
            try:
                print('''
● CLEAN DATA
——————————————————————————————————————————————————————————————————————————''')
                if FlowData.CleanType == "2Step" and FlowData.MissingActors:
                    print("  - 2-STEP PROCESS TERMINATED DUE TO MISSING OBJECTS -")
                print("  Model    (","Target:",FlowData.MainObjName,", Source:",FlowData.DupeObjName,", ModelType:",FlowData.ModelType,")")

                if mytool.CommonUV and len(FlowData.CommonUVObjects) >0: stmt = ", CommonUV: True "+str(FlowData.CommonUVObjects)
                else:stmt = ", CommonUV: False"
                print("  Options  ( CleanType:",FlowData.CleanType,stmt,", CleanGeo/BakeTex:",mytool.CleanGeo,"/",mytool.BakeTex,", Clean/BakeTimes:",FlowData.CleanTimes,"/",FlowData.BakeTimes,")")

                print("  Cleaning (","Initial:",FlowData.VertexCountInitialX,", Final:",FlowData.VertexCountFinalX,", Reduction:",round(100-(FlowData.VertexCountFinalX*100/max(1, FlowData.VertexCountInitialX)),1),"%",")")

                if FlowData.ModelType == "Voxel":
                    print("  Geometry (","SmallestEdge:",FlowData.SmallestEdgeLength,", LargestEdge:",FlowData.LargestEdgeLength,", BlocksInLargestEdge:",FlowData.LargestEdgeBlocks,")")

                    print("  Image    (","ApproxLen:",round(FlowData.ApproxLen,2),", ResolutionSet:",mytool.ResolutionSet,", AutoRes:",FlowData.AutoRes,", UpscaleFactor:",mytool.TextureScaleMultiplier,", FinalTextureSize:",FlowData.FinalTextureSize,")")
                
                    print("  UV       (","LargestUVEdgeLength(px):",FlowData.LargestUVEdgeLengthInPixels,", ResizeFactor:",FlowData.ResizeFactor,", RescaledLength(px):",FlowData.LargestUVEdgeLengthInPixels*FlowData.ResizeFactor,")","")
                else:
                    print("  Image    (","FinalTextureSize:",FlowData.FinalTextureSize," , Margin: 1/128 , Bleed:",FlowData.Bleed,")")
                
                print("  Bakelist (",str(FlowData.BakeList),")")
                #print("\n")
                print("\n  Process Ended GGs ———————————————————————————————————————————————————————")
                print("\n\n")

            except Exception as e: 
                print(e)

        #Handle the backup
        if (FlowData.CleanType == "2Step" and not FlowData.MissingActors) or (FlowData.CleanType == "Lazy"):
            
            # if the backup is to be preserved
            if mytool.CreateBackup == False: 
                FlowData.DupeObj.hide_set(False)
                bpy.ops.object.select_all(action='DESELECT')
                FlowData.DupeObj.select_set(True)
                bpy.context.view_layer.objects.active = FlowData.DupeObj
                bpy.ops.object.delete(use_global=False)
            else:

                # check for the the organisation option.
                if mytool.OrganiseBackups: #Organise models in a backup collection
                    # Find the backup collection. 
                    BackupModelCollection = bpy.data.collections.get("Vox Cleaner Backups")

                    # handle the BackupCollection instnace
                    if BackupModelCollection:   # it exists
                        try: bpy.context.scene.collection.children.link(BackupModelCollection)
                        except: pass
                    else:   # create & link to scene collection
                        BackupModelCollection = bpy.data.collections.new("Vox Cleaner Backups")
                        bpy.context.scene.collection.children.link(BackupModelCollection)
                        bpy.context.view_layer.layer_collection.children.get("Vox Cleaner Backups").exclude = True

                    # add dupe models/model to the collection
                    for Model in FlowData.CommonUVDupeObjects:
                        for OtherCollections in Model.users_collection: OtherCollections.objects.unlink(Model)
                        if Model.name not in BackupModelCollection.objects: BackupModelCollection.objects.link(Model)
                else: #just hide all them models
                    for Model in FlowData.CommonUVDupeObjects: 
                        Model.hide_set(True)
                
                        
            
        # Clear Existing FlowData n MetaData
        FlowData.ModelType = None
        FlowData.MainObj = None
        FlowData.MainObjName = None
        FlowData.DupeObj = None
        FlowData.DupeObjName = None
        FlowData.ObjArray = None
        FlowData.CommonUVObjects = []
        FlowData.CommonUVDupeObjects = []
        FlowData.CommonUVOrigins = {}

        FlowData.VertexCountInitialX = 0
        FlowData.VertexCountFinalX = 0
        
        FlowData.SmallestEdge = None
        FlowData.SmallestEdgeLength = 10000000.0

        FlowData.LargestEdge = None
        FlowData.LargestEdgeLength = 0.0
        FlowData.LargestEdgeBlocks = 0
        FlowData.LargestUVEdgeLengthInPixels = 0.0
        FlowData.ResizeFactor = 0.0
        
        FlowData.ApproxLen = 0.0
        FlowData.AutoRes = 0
        FlowData.FinalTextureSize = 0.0
        FlowData.Bleed = 0.0

        FlowData.MaterialMaps = []
        FlowData.GeneratedTex_Active = None
        FlowData.BakeList = []

        FlowData.GeneratedTex_Color = None
        FlowData.GeneratedTex_Roughness = None
        FlowData.GeneratedTex_Metallic = None
        FlowData.GeneratedTex_Emisson = None
        FlowData.GeneratedTex_Transmission = None

        FlowData.CleanTimes = 0
        FlowData.BakeTimes = 0
        FlowData.CleanType = None
        FlowData.TwoStepCommonUV = False
        FlowData.ProcessRunning = False
        FlowData.MissingActors = False
        

    def GetTextures(context):
        #Get a list of exportable textures on a model ready. No duplicates. 
        
        NodeList = []
        mytool = context.scene.vox_tool

        def CheckforTexturesWithinModels(obj,MapKey):
            try:
                if obj.data.materials[0] != None:
                    if obj.data.materials[0].node_tree.nodes[MapKey] != None:
                        if obj.data.materials[0].node_tree.nodes[MapKey].type == 'TEX_IMAGE':
                            if obj.data.materials[0].node_tree.nodes[MapKey].image != None:
                                NodeList.append(obj.data.materials[0].node_tree.nodes[MapKey])
            except: pass

        for obj in bpy.context.selected_objects:
            if mytool.ExportColor == True:
                CheckforTexturesWithinModels(obj,"Color")
            
            if mytool.ExportRoughness == True:
                CheckforTexturesWithinModels(obj,"Roughness")

            if mytool.ExportMetallic == True:
                CheckforTexturesWithinModels(obj,"Metallic")

            if mytool.ExportEmission == True:
                CheckforTexturesWithinModels(obj,"Emission")

            if mytool.ExportTransmission == True:
                CheckforTexturesWithinModels(obj,"Transmission")

        return list(set(NodeList))

    def TextureExport(context):
        folder = os.path.realpath(bpy.path.abspath(context.scene.vox_tool.ExportLocation))
        images = sorted({node.image for node in VoxMethods.GetTextures(context)}, key=lambda image: image.name)
        names = batch.safe_names(image.name for image in images)
        for image in images:
            image.file_format = 'PNG'
            image.filepath_raw = os.path.join(folder, names[image.name] + '.png')
            image.save()
        return len(images)

class ApplyVColors(bpy.types.Operator):
    """Apply the mesh's vertex colors as the base color.
Specifically made for .PLY meshes, as they have vertex color data present.

This button is context sensitive & will only appear if you have a .PLY mesh selected that has vertex color data"""
    bl_idname = "voxcleaner.applyvertexcolors"
    bl_label = "Apply Vertex Colors"
    bl_options = {'UNDO'}

    def execute(self, context):

        VMaterial = VoxMethods.CreateCRMETS(context,True, False, False, False, False)
        
        if len(bpy.context.selected_objects) > 0:
            #remove then add the material to everyone
            for x in bpy.context.selected_objects:
                if x.type == 'MESH':
                    try:
                        if len(x.data.color_attributes)==1:
                            x.data.materials.clear()
                            x.data.materials.append(VMaterial)
                            VMaterial.node_tree.nodes["Color"].layer_name = x.data.color_attributes[0].name
                            #print("Added VC Mat")
                    except:
                        pass
                    
            
            if len(bpy.context.selected_objects) == 1:
                self.report({'INFO'}, "Vertex colors applied to selected object")
            else:
                self.report({'INFO'}, "Vertex colors applied to selected objects")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Select an object first")
            return {'CANCELLED'}


class LazyClean(batch.BatchOperator, bpy.types.Operator):
    """Lazy Clean selected models"""
    bl_idname = "voxcleaner.lazyclean"
    bl_label = "Easy Clean"
    bl_options = {'UNDO'}

    def execute(self, context):
        
        mytool = context.scene.vox_tool
        CleanStatus,StepStatus,ExportStatus = VoxMethods.MrChecker(context)
        
        if type(CleanStatus) == int:
            pass
        else:
            self.report({'WARNING'}, CleanStatus)
            return {'CANCELLED'}


        if CleanStatus > 1 and not mytool.CommonUV:
            return self.start_batch(context, 'clean')
        if any(not obj.data.polygons for obj in context.selected_objects):
            self.report({'WARNING'}, 'Selected mesh has no faces')
            return {'CANCELLED'}

        if CleanStatus > 1 and mytool.CommonUV:
            
            #Check for a mixed model set
            ModelType = VoxMethods.MrModelTypeChecker(context.selected_objects)
            if ModelType == "Mixed":
                self.report({'WARNING'}, "Mixed model set, select only one type of models")
                return {'CANCELLED'}
            
            # lazy Common UV
            FlowData.CleanType = "Lazy"
            FlowData.CommonUVObjects = [obj.name for obj in context.selected_objects]

            # continue Common UV
            FlowData.ModelType = ModelType
            VoxMethods.JoinModels(context)
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.object.mode_set(mode = 'OBJECT')

            # clean Selected Object ie Object Set 
            VoxMethods.ModelFixing(context)

            if mytool.BakeTex == True:
                VoxMethods.MaterialSetUp(context)
            
            if FlowData.ModelType == "Voxel":
                VoxMethods.UVProjection(context)

                if mytool.CleanGeo == True:
                    VoxMethods.GeometryCleanUp(context)
                
                VoxMethods.UVScaling(context)
            else:
                if mytool.CleanGeo == True:
                    VoxMethods.GeometryCleanUp(context)

                VoxMethods.UVProjection(context)
                
            #Get a vert count dammit
            FlowData.VertexCountFinalX = len(FlowData.MainObj.data.vertices)

            if mytool.BakeTex == True:
                VoxMethods.TextureBake(context)

            # Split both the objects
            VoxMethods.ApplySplitToBothObjects(context)

            #Give out a feedback
            PercentageCleaning = round(100-(FlowData.VertexCountFinalX*100/max(1, FlowData.VertexCountInitialX)),1)
            if FlowData.ModelType == "Voxel": stmnt = "Model Set cleaned! "+str(PercentageCleaning)+"% avg vertex reduction!"
            else: stmnt = str(FlowData.ModelType)+" Model Set cleaned! "+str(PercentageCleaning)+"% avg vertex reduction!"
            self.report({'INFO'}, stmnt)
            
            #Clean The Plate
            VoxMethods.EndProcess(context)
            
            return {'FINISHED'}
        
    
        else:
            # solo clean

            CleanPercentageArray = []
            ModelTypeSet = set()
            ObjArray = bpy.context.selected_objects
            if len(ObjArray)==1:
                
                FlowData.CleanType = "Lazy"

                # deselect everything
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.view_layer.objects.active = None
                
                #select ith obj
                bpy.context.view_layer.objects.active = ObjArray[0]
                ObjArray[0].select_set(True)
                if ObjArray[0].data.users > 1:
                    ObjArray[0].data = ObjArray[0].data.copy()
                FlowData.ModelType = VoxMethods.MrModelTypeChecker(context.selected_objects)
                
                # clean Selected Object
                VoxMethods.ModelFixing(context)
                ModelTypeSet.add(FlowData.ModelType)

                if mytool.BakeTex == True:
                    print("Material Set Up")
                    VoxMethods.MaterialSetUp(context)
                
                if FlowData.ModelType == "Voxel":
                    VoxMethods.UVProjection(context)

                    if mytool.CleanGeo == True:
                        VoxMethods.GeometryCleanUp(context)
                    
                    VoxMethods.UVScaling(context)
                else:
                    if mytool.CleanGeo == True:
                        VoxMethods.GeometryCleanUp(context)

                    VoxMethods.UVProjection(context)
                
                if mytool.BakeTex == True:
                    VoxMethods.TextureBake(context)
                
                #Get a vert count dammit
                FlowData.VertexCountFinalX = len(FlowData.MainObj.data.vertices)

                CleanPercentageArray.append(round(100-(FlowData.VertexCountFinalX*100/max(1, FlowData.VertexCountInitialX)),1))

                FlowData.CommonUVDupeObjects = [FlowData.DupeObj]
                VoxMethods.EndProcess(context)

            # select the object
            bpy.context.view_layer.objects.active = None
            bpy.context.view_layer.objects.active = ObjArray[0]
            bpy.ops.object.select_all(action='DESELECT')
            ObjArray[0].select_set(True)
                

            #Give out a feedback
            if len(CleanPercentageArray) == 1:     #Only one object was there
                PercentageCleaning = round(sum(CleanPercentageArray)/len(CleanPercentageArray),2)
                if list(ModelTypeSet)[0] == "Voxel": stmnt = "Model cleaned! "+str(PercentageCleaning)+"% vertex reduction!"
                else: stmnt = str(list(ModelTypeSet)[0])+" Model cleaned! "+str(PercentageCleaning)+"% vertex reduction!"
                self.report({'INFO'}, stmnt)
                return {'FINISHED'}

            elif len(CleanPercentageArray) > 1:    #Multiple objects were there
                AverageCleaning = round(sum(CleanPercentageArray)/len(CleanPercentageArray),1)
                if len(ModelTypeSet) >1: stmnt = "All Models cleaned! "+str(AverageCleaning)+"% avg vertex reduction!"
                else:
                    if list(ModelTypeSet)[0] == "Voxel": stmnt = "Models cleaned! "+str(AverageCleaning)+"% avg vertex reduction!"
                    else: stmnt = str(list(ModelTypeSet)[0]) + " Models cleaned! "+str(AverageCleaning)+"% avg vertex reduction!"
                    self.report({'INFO'}, stmnt)
            
            return {'FINISHED'}
            
class PrepareForBake(bpy.types.Operator):
    """Clean the model geometry, set-up a material and generate a new image texture and finally project pixel-perfect UVs"""
    
    bl_idname = "voxcleaner.prepareforbake"
    bl_label = "Prepare For Bake"
    bl_options = {'UNDO'}

    def execute(self, context):
        mytool = context.scene.vox_tool
        CleanStatus,StepStatus,ExportStatus = VoxMethods.MrChecker(context)
        
        # warnings & errors
        if type(StepStatus) != int:
            self.report({'WARNING'}, StepStatus)
            return {'CANCELLED'}
        
        if FlowData.ProcessRunning == True and FlowData.CleanTimes>=1:
            self.report({'WARNING'}, "A 2 Step Process is running. Finish that first.")
            return {'CANCELLED'}
        
        # Set vertex snapping to disabled before starting process
        for Screen in bpy.data.screens:
            for area in Screen.areas:
                if area.type == 'IMAGE_EDITOR' and area.ui_type == 'UV':
                    area.spaces.active.uv_editor.pixel_round_mode = 'DISABLED'

        if StepStatus > 1:
            #Check for a mixed model set
            ModelType = VoxMethods.MrModelTypeChecker(context.selected_objects)
            if ModelType == "Mixed":
                self.report({'WARNING'}, "Mixed model set, select only one type of models")
                return {'CANCELLED'}
            
            # Common UV cleaning
            FlowData.TwoStepCommonUV = True
            FlowData.CleanType = "2Step"
            FlowData.ProcessRunning = True
            FlowData.CommonUVObjects = [obj.name for obj in context.selected_objects]
            
            # COntinue Common UV
            FlowData.ModelType = ModelType
            VoxMethods.JoinModels(context)
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.object.mode_set(mode = 'OBJECT')

            # clean Selected Object ie Object Set 
            VoxMethods.ModelFixing(context)

            VoxMethods.MaterialSetUp(context)
            
            if FlowData.ModelType == "Voxel":
                VoxMethods.UVProjection(context)

                if mytool.CleanGeo == True:
                    VoxMethods.GeometryCleanUp(context)
                
                VoxMethods.UVScaling(context)
            else:
                if mytool.CleanGeo == True:
                    VoxMethods.GeometryCleanUp(context)

                VoxMethods.UVProjection(context)
                
            #Get a vert count dammit
            FlowData.VertexCountFinalX = len(FlowData.MainObj.data.vertices)

            # Set vertex snapping to pixel
            for Screen in bpy.data.screens:
                for area in Screen.areas:
                    if area.type == 'IMAGE_EDITOR' and area.ui_type == 'UV':
                        area.spaces.active.uv_editor.pixel_round_mode = 'CORNER'

            FlowData.CleanTimes = FlowData.CleanTimes+1
            # Give out a feedback
            stmnt = "Ready For Shared Texture Bake! "+str(round(100-(FlowData.VertexCountFinalX*100/max(1, FlowData.VertexCountInitialX)),1))+"% vertex reduction!"
            self.report({'INFO'}, stmnt)
            return {'FINISHED'}


        if StepStatus == 1:
            # Single Model Cleaning
            FlowData.CleanType = "2Step"
            FlowData.ProcessRunning = True

            FlowData.ModelType = VoxMethods.MrModelTypeChecker(context.selected_objects)
            VoxMethods.ModelFixing(context)
            VoxMethods.MaterialSetUp(context)
            
            if FlowData.ModelType == "Voxel":
                VoxMethods.UVProjection(context)
                if mytool.CleanGeo == True: VoxMethods.GeometryCleanUp(context)
                VoxMethods.UVScaling(context)
            else:
                if mytool.CleanGeo == True: VoxMethods.GeometryCleanUp(context)
                VoxMethods.UVProjection(context)
            
            FlowData.VertexCountFinalX = len(FlowData.MainObj.data.vertices)

            # Set vertex snapping to pixel
            for Screen in bpy.data.screens:
                for area in Screen.areas:
                    if area.type == 'IMAGE_EDITOR' and area.ui_type == 'UV':
                        area.spaces.active.uv_editor.pixel_round_mode = 'CORNER'

            FlowData.CleanTimes = FlowData.CleanTimes+1
            # Give out a feedback
            stmnt = "Ready For Texture Bake! "+str(round(100-(FlowData.VertexCountFinalX*100/max(1, FlowData.VertexCountInitialX)),1))+"% vertex reduction!"
            self.report({'INFO'}, stmnt)
            return {'FINISHED'}

class PostUVBake(bpy.types.Operator):
    """Bake the texture from the Source model to the Target model.
Might take some time depending on the model's voxel density"""
    bl_idname = "voxcleaner.postuvbake"
    bl_label = "Bake Texture"
    bl_options = {'UNDO'}

    def execute(self, context):
        mytool = context.scene.vox_tool
        CleanStatus,StepStatus,ExportStatus = VoxMethods.MrChecker(context)

        # warnings & errors
        if not FlowData.ProcessRunning:
            self.report({'WARNING'}, "Prepare a model for bake first!")
            return {'CANCELLED'}
            
        if FlowData.CleanTimes == 0:
            self.report({'WARNING'}, "Prepare a model for bake first!")
            return {'CANCELLED'}

        if FlowData.MissingActors:
            self.report({'WARNING'}, "Missing Objects! Re-do The process!")
            return {'CANCELLED'}
        
        # Texture Bake
        VoxMethods.TextureBake(context)
        FlowData.BakeTimes = FlowData.BakeTimes+1

        # Give out a feedback
        stmt = "Shared Texture Bake Done!" if FlowData.TwoStepCommonUV else "Texture Bake Done!"
        self.report({'INFO'}, stmt)
        return {'FINISHED'}

            
        
class VoxTerminate(bpy.types.Operator):
    """Finish the ongoing 2-Step process"""
    bl_idname = "voxcleaner.terminate"
    bl_label = "Finish Cleaning"
    bl_options = {'UNDO'}

    def execute(self, context):
        
        # warnings & errors
        if not FlowData.ProcessRunning:
            self.report({'WARNING'}, "2-Step Process is not running!")
            return {'CANCELLED'}
        
        if FlowData.TwoStepCommonUV and FlowData.MissingActors == False:
            # Split models and make a Dupe Set as well - errors possible due to missing objects
            try:
                # Split both the objects
                VoxMethods.ApplySplitToBothObjects(context)
            except error as e: print(e)
        
        # terminate cleaning
        if FlowData.MissingActors == True: stmt = "Cleaning process terminated Due to Missing Objects!"
        else: stmt = "Cleaning Done! Enjoy!"
        VoxMethods.EndProcess(context)
        self.report({'INFO'}, stmt)
        return {'FINISHED'}
        
            
        
class OpenExportFolder(bpy.types.Operator):
    """Open The specified Export Folder in OS"""
    bl_idname = "voxcleaner.openexportfolder"
    bl_label = "Open Export Folder"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        mytool = context.scene.vox_tool

        if len(mytool.ExportLocation) == 0:
            self.report({'WARNING'}, 'Please add an export folder')
            return {'CANCELLED'}

        ExportDirectory = os.path.realpath(bpy.path.abspath(mytool.ExportLocation))

        if not os.path.exists(ExportDirectory):
            self.report({'WARNING'}, 'Export Location does not exist, please add another location')
            return {'CANCELLED'}
            
        else:
            if sys.platform == "win32":
                os.startfile(ExportDirectory)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.call(["open",ExportDirectory])
            else:   #Linux and others
                try:
                    import subprocess
                    subprocess.Popen(['xdg-open', ExportDirectory])
                except:
                    self.report({'WARNING'}, 'Sorry, Seems like you have an unsupported Operating System')
                    return {'CANCELLED'}
                        
        return {'FINISHED'}
    

def export_one(context, obj, format, filename):
    folder = os.path.realpath(bpy.path.abspath(context.scene.vox_tool.ExportLocation))
    path = os.path.join(folder, filename + '.' + format)
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        if format == 'obj':
            result = bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True,
                forward_axis='NEGATIVE_Z', up_axis='Y', export_animation=False,
                apply_modifiers=True, export_materials=True,
                export_triangulated_mesh=context.scene.vox_tool.TriangulatedExport,
                path_mode='AUTO')
        else:
            result = bpy.ops.export_scene.fbx(filepath=path, use_selection=True,
                apply_scale_options='FBX_SCALE_ALL', bake_anim=False,
                use_triangles=context.scene.vox_tool.TriangulatedExport, path_mode='AUTO')
        if result != {'FINISHED'} or not os.path.isfile(path) or not os.path.getsize(path):
            raise RuntimeError(f'Export failed: {path}')
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for item in selected:
            item.select_set(True)
        context.view_layer.objects.active = active


class ExportMeshes(batch.BatchOperator):
    def execute(self, context):
        status = VoxMethods.MrChecker(context)[2]
        if not isinstance(status, int):
            self.report({'WARNING'}, status)
            return {'CANCELLED'}
        folder = context.scene.vox_tool.ExportLocation
        if not folder or not os.path.isdir(bpy.path.abspath(folder)):
            self.report({'WARNING'}, 'Choose an existing export folder')
            return {'CANCELLED'}
        if status > 1:
            return self.start_batch(context, self.export_format)
        try:
            count = VoxMethods.TextureExport(context)
            obj = context.selected_objects[0]
            export_one(context, obj, self.export_format, batch.safe_names([obj.name])[obj.name])
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, f'1 {self.export_format.upper()} and {count} textures exported')
        return {'FINISHED'}


class ExportOBJ(ExportMeshes, bpy.types.Operator):
    """Export one OBJ per selected mesh, with textures"""
    bl_idname = "voxcleaner.exportobj"
    bl_label = "Export OBJ"
    export_format = 'obj'


class ExportFBX(ExportMeshes, bpy.types.Operator):
    """Export one FBX per selected mesh, with textures"""
    bl_idname = "voxcleaner.exportfbx"
    bl_label = "Export FBX"
    export_format = 'fbx'

class ResetSettings(bpy.types.Operator):
    """Reset all settings in this add-on"""
    bl_idname = "voxcleaner.resetsettings"
    bl_label = "Reset Settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        mytool = context.scene.vox_tool
        mytool.BatchWorkers = 0
        mytool.BaseColor = StaticData.BaseColorDefault
        mytool.AlphaBool = StaticData.AlphaDefault
        mytool.ResolutionSet = StaticData.ResolutionDefault
        mytool.TextureScaleMultiplier = StaticData.UpscalingDefault
        mytool.UVMethod = StaticData.UVMethodDefault
        mytool.RotateUV = StaticData.RotateUVDefault

        mytool.MCNVResolution = StaticData.MCNVResDefault
        mytool.NVDecimation = StaticData.NVDecimationDefault

        mytool.CreateBackup = StaticData.ModelBackupDefault
        mytool.OrganiseBackups = StaticData.OrganiseDefault
        mytool.TriangulatedExport = StaticData.TriangulateDefault
        mytool.EmitStrength = StaticData.EmitStrengthDefault

        return {'FINISHED'} 
    
class CheckForUpdates(bpy.types.Operator):
    """Open the upstream Vox Cleaner page; see the fork README for this build"""
    bl_idname = "voxcleaner.checkforupdates"
    bl_label = "Upstream Updates"

    def execute(self, context):

        webbrowser.open('https://thestrokeforge.gumroad.com/l/VoxCleanerV3')

        return {'FINISHED'} 



# UI Panels  ######################################################################################################################################################################################################## UI Panels
    
class VoxImport(bpy.types.Panel):
    #bl_parent_id = "VoxCleaner_PT_main_panel"
    bl_label = "Import"
    bl_idname = "IMPORT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Vox Cleaner"
    
    
    def draw_header(self, _):
        layout = self.layout
        layout.label(text="", icon='IMPORT')

    def draw(self, context):
        layout = self.layout

        # MainButton Box
        box = layout.box()
        row = box.row()
        row.scale_y = StaticData.BigButtonHeight
        row.operator("voxcleaner.importvox",icon = 'FILE_3D')


class VoxClean(bpy.types.Panel):
    #bl_parent_id = "VoxCleaner_PT_main_panel"
    bl_label = "Cleaner"
    
    bl_idname = "CLEANER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Vox Cleaner"
    
    
    def draw_header(self, _):
        layout = self.layout
        layout.label(text="", icon='SHADERFX')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.vox_tool
        
        # Apply Vert Colors button
        ShowVertexColorsButton = False
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                if len(obj.data.color_attributes) ==1:

                    if obj.data.color_attributes[0] != None:
                    # there's an object that can have the vert color material
                        ShowVertexColorsButton = True
                        break
        else:ShowVertexColorsButton = False        
                    
        if ShowVertexColorsButton == True:
            row = layout.row()
            row.scale_y = 1.2
            row.operator("voxcleaner.applyvertexcolors", icon = 'MATERIAL')


        # Common UV Button
        CommonUVRow = layout.row()
        CommonUVRow.scale_y = 1

        CommonUVRow.prop(mytool, "CommonUV")

        CleanStatus,StepStatus, ExportStatus = VoxMethods.MrChecker(context)

        if FlowData.ProcessRunning == False:CommonUVRow.enabled = True
        else:CommonUVRow.enabled = False

        # Main Button Boox
        box = layout.box()
        row = box.row()
        row.scale_y = StaticData.CleanModePaneHeight
        row.prop(mytool, "CleanMode", expand=True)
        row.enabled = True if FlowData.ProcessRunning == False else False

        if mytool.CleanMode == 'ez':
            col = box.column()
            row = col.row(align = False)
            row.prop(mytool, "CleanGeo")
            row.prop(mytool, "BakeTex")
            if type(CleanStatus) == int or CleanStatus == "Select atleast one options above to clean": row.enabled = True
            else: row.enabled = False

            row = col.row(align = False)
            row.scale_y = StaticData.BigButtonHeight
            if type(CleanStatus) == int:
                if CleanStatus == 1:
                    row.operator("voxcleaner.lazyclean",icon = 'SOLO_ON',text = 'Clean Model')
                else:
                    if mytool.CommonUV == True:
                        row.operator("voxcleaner.lazyclean",icon = 'COLOR',text = 'Clean with Shared UVs')
                    else:
                        row.operator("voxcleaner.lazyclean", icon='SOLO_ON', text=f'Clean {CleanStatus} Models')
            else:
                row.label(icon="ERROR", text = CleanStatus)

        if mytool.CleanMode == 'hard':

            # Process Running Live View wo Clean Geo Toggle
            if FlowData.ProcessRunning:
                try: Trg = str(FlowData.MainObj.name)
                except:
                    Trg = "- Missing Object -"
                    FlowData.MissingActors = True
                try: Src = str(FlowData.DupeObj.name)
                except:
                    Src = "- Missing Object -"
                    FlowData.MissingActors = True
                    
                # Target and Source display + Clean Geo Button
                HardCol = box.column(align = True)
                ScreenRow = HardCol.row()

                # Model Names
                labels = HardCol.column(align = True)
                labels.alignment = "EXPAND"
                labels.enabled = True if FlowData.ProcessRunning  == True else False
                
                labels.label(text = "Target:  " + Trg)
                labels.label(text = "Source:  " + Src)
            else:
                # Process Not running Stale View + Clean Geo Toggle
                
                # Target and Source display + Clean Geo Button
                HardCol = box.column(align = True)
                ScreenRow = HardCol.row()
                split = ScreenRow.split(factor = 0.5)

                # Model Names
                labels = split.column(align = True)
                labels.alignment = "EXPAND"
                labels.enabled = True if FlowData.ProcessRunning  == True else False
                
                labels.label(text = "Target:  None")
                labels.label(text = "Source:  None")

                # Clean geo toggle
                props = split.column(align = True)
                CleanToggleEnabled = not(FlowData.ProcessRunning) and type(StepStatus) == int
                props.enabled = CleanToggleEnabled
                props.label(text = "   ")
                props.prop(mytool, "CleanGeo") 

            if type(StepStatus) == int:
                
                # Spacing
                row = HardCol.row()      
                row.label(text = "   ")               
                row.scale_y = StaticData.SeperatorSpacing3
                
                # Prepare for Bake
                row = HardCol.row()
                if FlowData.ProcessRunning == True and FlowData.CleanTimes>=1: row.enabled = False
                else: row.enabled = True
                row.scale_y = StaticData.BigButtonHeight
                if mytool.CommonUV == True and StepStatus >1: row.operator("voxcleaner.prepareforbake", icon = 'TOOL_SETTINGS',text = 'Prepare for Shared UV Clean')
                else: row.operator("voxcleaner.prepareforbake", icon = 'TOOL_SETTINGS')
                
                # Spacing
                row = HardCol.row()      
                row.label(text = "   ")               
                row.scale_y = StaticData.SeperatorSpacing2
                
                # Bake Texture
                row = HardCol.row()
                if FlowData.ProcessRunning == True and FlowData.CleanTimes>=1 and FlowData.MissingActors == False: row.enabled = True
                else: row.enabled = False
                row.scale_y = StaticData.BigButtonHeight
                if mytool.CommonUV and StepStatus >1: row.operator("voxcleaner.postuvbake",icon = 'TEXTURE_DATA',text = "Bake Shared Textures")
                else: row.operator("voxcleaner.postuvbake",icon = 'TEXTURE_DATA')

                # Terminate Button
                if FlowData.ProcessRunning:
                    # spacing
                    row = HardCol.row()      
                    row.label(text = "   ")               
                    row.scale_y = StaticData.SeperatorSpacing1-StaticData.SeperatorSpacing3
                    
                    row = HardCol.row()
                    row.operator("voxcleaner.terminate",icon = 'CHECKMARK')
            else:
                # Spacing
                row = HardCol.row()      
                row.label(text = "   ")               
                row.scale_y = StaticData.SeperatorSpacing4
                
                
                row = HardCol.row()
                row.label(icon = "ERROR", text = StepStatus)  
                row.scale_y = StaticData.BigButtonHeight*2 + StaticData.SeperatorSpacing2


class VoxExport(bpy.types.Panel):
    #bl_parent_id = "VoxCleaner_PT_main_panel"
    bl_label = "Export"
    bl_idname = "EXPORT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Vox Cleaner"
    bl_options = {'DEFAULT_CLOSED'}
    
    
    def draw_header(self, _):
        layout = self.layout
        layout.label(text="", icon='FOLDER_REDIRECT')

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        mytool = scene.vox_tool

        #Export Location & Open Folder
        col = layout.column()
        
        split = col.split(factor = StaticData.VerticalSplitFactor)

        labels = split.column()
        labels.alignment = "RIGHT"
        labels.label(text = "Export Folder:")
        props = split.column()
        props.prop(mytool, "ExportLocation")
        row = col.row()
        row.scale_y = 1.2
        row.operator("voxcleaner.openexportfolder",icon = 'FILEBROWSER')

        #Spacing needed
        spacing = col.row()
        spacing.scale_y = StaticData.SeperatorSpacing1
        spacing.label(text = " ")

        # Export Maps
        header, panel = layout.panel("ExportSub", default_closed=True)
        BracketText = ""

        if mytool.ExportColor: BracketText+="C"
        if mytool.ExportRoughness: BracketText+="R"
        if mytool.ExportMetallic: BracketText+="M"
        if mytool.ExportEmission: BracketText+="E"
        if mytool.ExportTransmission: BracketText+="T"
        
        if BracketText == "CRMET": BracketText = "All"
        if BracketText == "": BracketText = "None"
        
        header.label(icon='NODE_COMPOSITING',text = str("Map Exports (" + BracketText + ")"))
        if panel:
            row = panel.row()
            col = row.column(align = True)

            col = row.column(align = True)
            col.prop(mytool, "ExportColor")
            col.prop(mytool, "ExportRoughness")
            col.prop(mytool, "ExportMetallic")

            col = row.column(align = True)
            col.prop(mytool, "ExportEmission")
            col.prop(mytool, "ExportTransmission")

        #MainButtonBox
        box = layout.box()

        CleanStatus,StepStatus, ExportStatus = VoxMethods.MrChecker(context)
        col = box.column()

        SummaryRow = col.row()
        SummaryRow.label(text = str(VoxMethods.ExportSummaries(context)))
        SummaryRow.enabled = True if type(ExportStatus) == int else False

        row = col.row()
        row.scale_y = StaticData.BigButtonHeight
        if type(ExportStatus) == int:
            #split = box.split()
            
            if ExportStatus == 1:
                
                #row.operator("voxcleaner.exportobj",icon = 'SNAP_FACE',text = "OBJ")
                row.operator("voxcleaner.exportfbx",icon = 'SNAP_FACE',text = "FBX")
                row.operator("voxcleaner.exportobj",icon = 'SNAP_FACE',text = "OBJ")
            elif ExportStatus >1:
                #row.operator("voxcleaner.exportobj",icon = 'SNAP_VERTEX',text = "OBJs")
                row.operator("voxcleaner.exportfbx",icon = 'SNAP_VERTEX',text = "FBXs")
                row.operator("voxcleaner.exportobj",icon = 'SNAP_VERTEX',text = "OBJs")
                
        else:
            row.label(icon="ERROR", text = ExportStatus)


class VoxSettings(bpy.types.Panel):
    #bl_parent_id = "VoxCleaner_PT_main_panel"
    bl_label = "General Settings"
    
    bl_idname = "SETTINGS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Vox Cleaner"
    bl_options = {'DEFAULT_CLOSED'}
    
    
    def draw_header(self, _):
        layout = self.layout
        layout.label(text="", icon='PREFERENCES')

    def draw(self, context):

        # Model Settings ------------------------------------------------------------------
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True

        scene = context.scene
        mytool = scene.vox_tool
        
        # Model Settings Panel
        col = layout.column()
        col.prop(mytool, "BatchWorkers")
        col.label(text = "Model Settings",icon = 'OBJECT_DATA')
        
        box = col.box()
        ROW = box.row(align = True)

        split = ROW.split(factor = StaticData.VerticalSplitFactor)

        labels = split.column()
        labels.alignment = "RIGHT"
        labels.label(text = "Base Color:")
        labels.label(text = "Base Image has Aplha:")

        props = split.column()
        props.prop(mytool, "BaseColor")
        props.prop(mytool, "AlphaBool")


        # Voxel Models
        header, panel = box.panel("VoxelMods", default_closed=False)
        header.label(icon='FILE_3D',text = "Voxel Models")
        if panel:
            row = panel.row(align = True)

            split = row.split(factor = StaticData.VerticalSplitFactor)

            labels = split.column(align = True)
            labels.alignment = "RIGHT"  
            labels.label(text = "Resolution Set (px):")
            labels.label(text = "Resolution Upscaling:")
            
            #Spacing
            row = labels.row()      
            row.label(text = "   ")               
            row.scale_y = StaticData.SeperatorSpacing1
            
            labels.label(text = "UV Projection Method:")
            labels.label(text = "Rotate UV Islands:")
            
            props = split.column(align = True)
            labels.alignment = "LEFT"
            props.prop(mytool, "ResolutionSet")
            props.prop(mytool, "TextureScaleMultiplier")
            
            #Spacing
            row = props.row()      
            row.label(text = "   ")               
            row.scale_y = StaticData.SeperatorSpacing1
            
            props.prop(mytool, "UVMethod")
            props.prop(mytool, "RotateUV")

        
        # MC+Non-Voxel Models
        header, panel = box.panel("MCNVMods", default_closed=False)
        header.label(icon='MONKEY',text = "MC & Non-Voxel Models")
        if panel:
            row = panel.row(align = False)

            split = row.split(factor = StaticData.VerticalSplitFactor)

            labels = split.column()
            labels.alignment = "RIGHT"  
            labels.label(text = "Resolutions:")
            labels.label(text = "Non-Voxel Decimation:")
            
            props = split.column(align = False)
            props.prop(mytool, "MCNVResolution")
            props.prop(mytool, "NVDecimation")      
        
        spacing = col.row()
        spacing.scale_y = StaticData.SeperatorSpacing2
        spacing.label(text = " ")
        
        # Preferences ------------------------------------------------------------------
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = False
        
        col = layout.column()
        col.label(text = "Preferences",icon = 'PROPERTIES')

        box = col.box()
        COL = box.column(align = True)

        COL.prop(mytool, "CreateBackup")
        
        BackupFolderRow = COL.row()
        BackupFolderRow.prop(mytool, "OrganiseBackups")
        BackupFolderRow.enabled = True if mytool.CreateBackup == True else False

        COL.prop(mytool, "TriangulatedExport")

        split = COL.split(factor = StaticData.VerticalSplitFactor)

        labels = split.column()
        labels.alignment = "RIGHT"
        labels.label(text = "Default Emit Strength:")

        props = split.column()
        props.prop(mytool, "EmitStrength")


        row = col.row()
        row.scale_y = StaticData.ButtonHeightMedium
        row.operator("voxcleaner.resetsettings",icon = 'FILE_REFRESH')

        spacing = col.row()
        spacing.scale_y = StaticData.SeperatorSpacing2
        spacing.label(text = " ")

        row = col.row()
        row.scale_y = StaticData.BigButtonHeight
        row.operator("voxcleaner.checkforupdates",icon = 'URL')




classes = [ApplyVColors,VoxProperties,LazyClean,PrepareForBake,PostUVBake,VoxTerminate,VoxImport,VoxClean,VoxExport,VoxSettings,ImportVox,ExportOBJ,ExportFBX,OpenExportFolder,ResetSettings,CheckForUpdates]
 
def menu_func_import(self, context):
    self.layout.operator(ImportVox.bl_idname, icon = "FILE_3D",text="MagicaVoxel (.vox)")


def register():
    batch.register()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.Scene.vox_tool = bpy.props.PointerProperty(type= VoxProperties)

        
def unregister():
    batch.unregister()
    del bpy.types.Scene.vox_tool
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    
 
if __name__ == "__main__":
    register()