import maya.cmds as cmds
import os
import re
from collections import defaultdict

# ---------- DATA STRUCTURE ----------

class ArnoldSurfaceMat:
    def __init__(self, name):
        self.name = name
        self.baseColor = None
        self.normal = None
        self.roughness = None
        self.metalness = None
        self.height = None
        self.opacity = None
        self.emission = None
        self.ao = None
        self.specular = None
        self.transmission = None
        self.sss = None

    def __repr__(self):
        return f"<ArnoldSurfaceMat name={self.name}>"

# ---------- GET TEXTURES FROM SOURCEIMAGES ----------

def get_textures_from_sourceimages():
    sourceimages_path = os.path.join(cmds.workspace(q=True, rd=True), "sourceimages")
    texture_extensions = [".jpg", ".png", ".tif", ".tga", ".exr", ".jpeg", ".bmp"]

    textures = []

    for root, _, files in os.walk(sourceimages_path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in texture_extensions):
                textures.append(os.path.join(root, f).replace("\\", "/"))

    return textures

# ---------- GROUP TEXTURES BY MATERIAL ----------

def create_arnold_material_array():
    textures = get_textures_from_sourceimages()

    materials = {}

    for tex_path in textures:
        fname = os.path.basename(tex_path)

        # Match pattern ignoring case, but keep original fname for mat_key
        match = re.match(r"^(.*?)(_basecolor|_albedo|_roughness|_metalness|_normal|_height|_disp)", fname, re.IGNORECASE)
        if not match:
            continue

        mat_key = match.group(1)  # Keep original case

        if mat_key not in materials:
            materials[mat_key] = ArnoldSurfaceMat(mat_key)

        mat = materials[mat_key]
        lower = fname.lower()

        if "_basecolor" in lower or "_albedo" in lower:
            mat.baseColor = tex_path
        elif "_roughness" in lower:
            mat.roughness = tex_path
        elif "_metalness" in lower or "_metal" in lower:
            mat.metalness = tex_path
        elif "_normal" in lower:
            mat.normal = tex_path
        elif "_height" in lower or "_disp" in lower:
            mat.height = tex_path
        elif "_opacity" in lower or "_alpha" in lower or "_transparency" in lower:
            mat.opacity = tex_path
        elif "_emissive" in lower or "_emission" in lower or "_selfillum" in lower:
            mat.emission = tex_path
        elif "_ao" in lower or "_ambientocclusion" in lower:
            mat.ao = tex_path
        elif "_specular" in lower:
            mat.specular = tex_path
        elif "_transmission" in lower or "_glass" in lower:
            mat.transmission = tex_path
        elif "_sss" in lower or "_subsurface" in lower:
            mat.sss = tex_path

    return list(materials.values())

# ---------- APPLY TEXTURES TO MATERIAL ----------

default_mats = {"lambert1", "standardSurface1", "openPBR_shader1", "particleCloud1", "shaderGlow"}

def apply_textures_to_materials(materials):
    for mat in materials:
        
        mat_name = os.path.splitext(os.path.basename(mat.name))[0]
        while not cmds.objExists(mat_name) and "_" in mat_name:
            if not cmds.objExists(mat_name):
                mat_name = mat_name.replace("_", ":", 1)
            if not cmds.objExists(mat_name):
                if ":" in mat_name:
                    mat_name = mat_name.split(":", 1)[1]
                    
#        if not cmds.objExists(mat_name):
#            mat_name = mat_name.replace("_", ":", 1);
#            if not cmds.objExists(mat_name):
#                continue
                
        if not cmds.objExists(mat_name):
            continue

        shader = mat_name
        shading_group = cmds.listConnections(shader, type="shadingEngine")

        if not shading_group or mat_name in default_mats:
            continue
        else:
            shading_group = shading_group[0]

        # === BaseColor ===
        if mat.baseColor:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_BaseColor_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.baseColor, type="string")
            cmds.connectAttr(tex + ".outColor", shader + ".baseColor", force=True)

        # === Roughness ===
        if mat.roughness:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_Roughness_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.roughness, type="string")
            cmds.connectAttr(tex + ".outColorR", shader + ".specularRoughness", force=True)
            cmds.connectAttr(tex + ".outColorR", shader + ".diffuseRoughness", force=True)

        # === Metalness ===
        if mat.metalness:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_Metalness_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.metalness, type="string")
            cmds.connectAttr(tex + ".outColorR", shader + ".metalness", force=True)

        # === Normal Map ===
        if mat.normal:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_Normal_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.normal, type="string")
            cmds.setAttr(tex + ".colorSpace", "Raw", type="string")
            normal_map = cmds.shadingNode("aiNormalMap", asUtility=True, name=f"{shader}_NormalMap")
            cmds.connectAttr(tex + ".outColor", normal_map + ".input", force=True)
            cmds.connectAttr(normal_map + ".outValue", shader + ".normalCamera", force=True)

        # === Height / Displacement ===
        if mat.height:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{mat_name}_Height_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.height, type="string")
            cmds.setAttr(tex + ".colorSpace", "Raw", type="string")
        
            disp_name = f"{mat_name}_Displacement"
            
            # Check if displacement shader already exists
            if not cmds.objExists(disp_name):
                disp = cmds.shadingNode("displacementShader", asShader=True, name=disp_name)
                cmds.setAttr(disp + ".scale", 0.01)
            else:
                disp = disp_name  # just use existing one
        
            # Connect texture to displacement shader
            if not cmds.isConnected(tex + ".outColorR", disp + ".displacement"):
                cmds.connectAttr(tex + ".outColorR", disp + ".displacement", force=True)
        
            # Connect displacement shader to shading group
            if not cmds.isConnected(disp + ".displacement", shading_group + ".displacementShader"):
                cmds.connectAttr(disp + ".displacement", shading_group + ".displacementShader", force=True)
               
        # === Opacity ===
        if mat.opacity:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_Opacity_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.opacity, type="string")
            cmds.setAttr(tex + ".colorSpace", "Raw", type="string")
            cmds.connectAttr(tex + ".outAlpha", shader + ".opacity", force=True)

        # === Emission ===
        if mat.emission:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_Emission_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.emission, type="string")
            cmds.connectAttr(tex + ".outColor", shader + ".emissionColor", force=True)
            cmds.setAttr(shader + ".emission", 1)

        # === Ambient Occlusion (AO) — optional use with baseColor
        if mat.ao and mat.baseColor:
            ao_tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_AO_tex")
            cmds.setAttr(ao_tex + ".fileTextureName", mat.ao, type="string")
            cmds.setAttr(ao_tex + ".colorSpace", "Raw", type="string")
            
            mult_node = cmds.shadingNode("aiMultiply", asUtility=True, name=f"{shader}_AO_Multiply")
            cmds.connectAttr(tex + ".outColor", mult_node + ".input1", force=True)   # baseColor
            cmds.connectAttr(ao_tex + ".outColor", mult_node + ".input2", force=True) # AO
            cmds.connectAttr(mult_node + ".outColor", shader + ".baseColor", force=True)

        # === Transmission ===
        if mat.transmission:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_Transmission_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.transmission, type="string")
            cmds.setAttr(tex + ".colorSpace", "Raw", type="string")
            cmds.connectAttr(tex + ".outColorR", shader + ".transmission", force=True)

        # === Subsurface scattering (SSS) ===
        if mat.sss:
            tex = cmds.shadingNode("file", asTexture=True, name=f"{shader}_SSS_tex")
            cmds.setAttr(tex + ".fileTextureName", mat.sss, type="string")
            cmds.connectAttr(tex + ".outColor", shader + ".subsurfaceColor", force=True)
            cmds.setAttr(shader + ".subsurface", 1)

        print(f"[✔] Textures connected for material: {mat.name}")

materials = create_arnold_material_array()
#Log all Texture got from sourceImages
#for mat in materials:
#    print("Material:", mat.name)
#    print("  BaseColor:", mat.baseColor)
#    print("  Normal:", mat.normal)
#    print("  Roughness:", mat.roughness)
#    print("  Metalness:", mat.metalness)
#    print("  Height:", mat.height)
#    print("---")
apply_textures_to_materials(materials)