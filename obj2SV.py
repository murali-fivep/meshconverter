#Custom converter for publishing Obj mesh models to Smithsonian Voyger format https://smithsonian.github.io/dpo-voyager/
#murali.fivep@gmail.com
#Input: 
# 1) Root folder path containing folders with 3D models in obj format (with single texture only)
# 2) Template .svx.json file in the root folder, with asset nodes Thumb, High, Medium, Low. To add more asset nodes, manually update the json template and edit generateLODS() method
#NOTE: As a quick and dirty hack, there is very little error handling

#pre-requisites: 
#install Meshlab https://www.meshlab.net/
#install Python https://www.python.org/
#install Meshlab Python bindings https://github.com/3DLIRIOUS/MeshLabXML
#install npm.js https://nodejs.org/en/download/
#install obj2gltf https://github.com/CesiumGS/obj2gltf

#imports
import meshlabxml as mlx
import glob
import os
import time
from PIL import Image
import json
import re
import sys
#---------------------------------------------------------------------------------------

#hardcoded globals
meshlabserver_path = "C:/Program Files/VCG/MeshLab" #path to Meshlab install location
#---------------------------------------------------------------------------------------

#resize the texture image file
#correct way would be to read OBJ file, get the MTL file and then get the image file
#assuming the file names are always same for all the three with different extensions
def imageresize(inputobj, outputobj, len):

    inputimage = next(glob.iglob(os.path.dirname(inputobj) + "/*.png"))

    if os.path.exists(inputimage) == False:
        print("ERROR: unable to find " + inputimage)
        return

    im = Image.open(inputimage)

    newfile = outputobj.replace(".obj", ".png")
    im.resize((len, len)).save(newfile)

    return newfile
#---------------------------------------------------------------------------------------

#update the mtl file with the path to the textire file
def updatemtl(outputobj, imagepath):
    mtlpath = next(glob.iglob(os.path.dirname(outputobj) + "/*.mtl"))
    
    if os.path.exists(mtlpath) == False:
        print("ERROR: unable to find " + mtlpath)
        return

    with open(mtlpath, "r") as mtl:
        lines = mtl.readlines()
    
    #there must be a simpler way to edit a line in a text file
    with open(mtlpath, "w") as mtl:
        for line in lines:
            if line.find("map_Kd")!= -1:
                line = "map_Kd " + os.path.basename(imagepath) + "\n"
            mtl.write(line)

#---------------------------------------------------------------------------------------

#convert to glB, uses https://github.com/CesiumGS/obj2gltf
def convert2glb(outputobj):    

    cmd = "obj2gltf -i " + "\"" + outputobj + "\" -o \"" + outputobj.replace(".obj", ".glb")  + "\"" + " --inputUpAxis \"Z\"" + " --outputUpAxis \"Z\""
    os.system(cmd)
#---------------------------------------------------------------------------------------

#simplfy mesh usign Meshlab - needs Meshlab to installed https://www.meshlab.net/
def simplifyMesh(inputobj, outputobj, facecount):
    print("converting: " + inputobj + " to glb with facecount: " + str(facecount))

    meshmodel = mlx.FilterScript(file_in=inputobj, file_out= outputobj)               
    mlx.remesh.simplify(meshmodel, texture = True, faces = facecount, preserve_boundary=True)
    meshmodel.run_script(print_meshlabserver_output=False)
    meshmodel.closing

#---------------------------------------------------------------------------------------

def updateMeshBounds(objpath, svx):
    
    aabb = mlx.files.measure_aabb(objpath, objpath + ".log")

    svx['models'][0]['boundingBox']['min'] = aabb['min']
    svx['models'][0]['boundingBox']['max'] = aabb['max']
#---------------------------------------------------------------------------------------

#update the template svx.json file with valid values
def updateSVX(glbpath, svx, quality, numfaces, imagesize):

    for derivative in svx['models'][0]['derivatives']:
        if derivative['quality'] == quality:
            derivative['assets'][0]['uri'] = os.path.basename(glbpath)
            derivative['assets'][0]['byteSize'] = os.path.getsize(glbpath)
            derivative['assets'][0]['numFaces'] = numfaces
            derivative['assets'][0]['imageSize'] = imagesize
#---------------------------------------------------------------------------------------

#generate LODs based on https://smithsonian.github.io/dpo-voyager/document/example/
def generateLODS(inputobj, outputpath, svx):

    filename = os.path.basename(outputpath) 

    lods = []
    
    #set the LOD details: filename, "LOD name", Num of mesh faces, Texture file size
    lods.append([outputpath + "/" + filename + "-20k-512-thumb.obj", "Thumb", 2000, 512])
    lods.append([outputpath + "/" + filename + "-150k-4096-high.obj","High", 15000, 4096])
    lods.append([outputpath + "/" + filename + "-150k-2048-medium.obj", "Medium", 15000, 2048])
    lods.append([outputpath + "/" + filename + "-150k-1024-low.obj", "Low", 15000, 1024])

    #generate LODs
    for lod in lods:
        simplifyMesh(inputobj, lod[0], lod[2])
        imagepath = imageresize(inputobj, lod[0], lod[3])
        updatemtl(lod[0], imagepath)
        convert2glb(lod[0])
        updateSVX(lod[0].replace(".obj", ".glb"), svx, lod[1], lod[2], lod[3])
    
    #update the bounding box, use smallest LOD to speed up processing
    updateMeshBounds(lods[0][0], svx)
#---------------------------------------------------------------------------------------

#looks for a template svx.json file in the input folder. eg. https://smithsonian.github.io/dpo-voyager/document/example/
def loadSVX(inputpath):
    svxpath = inputpath + "/.svx.json"
    if os.path.exists(svxpath) == False:
        print("ERROR: unable to find " + svxpath)
        return
    
    with open(svxpath) as f:
        svx = json.load(f)

    return svx
#---------------------------------------------------------------------------------------

def saveSVX(outputpath, svx):
    svxpath = outputpath + "/" + os.path.basename(outputpath) + ".svx.json"
    
    with open(svxpath, "w") as f:
        json.dump(svx, f)
#---------------------------------------------------------------------------------------

def purgeFiles(outpath):

    for path in glob.iglob(outpath + "/*.obj", recursive=True):
        os.remove(path)

    for path in glob.iglob(outpath + "/*.mtl", recursive=True):
        os.remove(path)

    for path in glob.iglob(outpath + "/*.png", recursive=True):
        os.remove(path)

    for path in glob.iglob(outpath + "/*.log", recursive=True):
        os.remove(path)

#---------------------------------------------------------------------------------------

def init():
    #HARDCODED set the path in the enviroment variable, else meshlabserver will not start
    os.environ["PATH"] = meshlabserver_path + os.pathsep + os.environ["PATH"]

    #read arguments for root folder path to the models
    if len(sys.argv) != 2:
        print('Argument missing: provide a root folder path to the models')
        return False
    
    rootinputpath = sys.argv[1]

    if os.path.exists(rootinputpath  + "/.svx.json") == False:
        print("ERROR: unable to find " + svxpath)
        return False

    #create an output path one level up 
    #do not allow user to specify the output path 
    #if root output path is a child of the inputpathroot, program will end up recursively process existing published models
    rootoutputpath = os.path.dirname(rootinputpath) + "/published/" + str(time.time()).replace(".", "") + "_Output_GlTF"
    os.makedirs(rootoutputpath)

    return [rootinputpath, rootoutputpath]
#---------------------------------------------------------------------------------------

#check for presence of OBJ, PNG and MTL files
def checkPaths(rootinputpath):

    try:
        next(glob.iglob(rootinputpath + "/*.png"))
    except StopIteration:
        return False

    try:
        next(glob.iglob(rootinputpath + "/*.obj"))
    except StopIteration:
        return False

    try:
        next(glob.iglob(rootinputpath + "/*.mtl"))
    except StopIteration:
        return False
    
    return True
#---------------------------------------------------------------------------------------

def publishToGLB(rootinputpath, rootoutputpath):

    #iterate the root path for models in individual folders 
    for objpath in glob.iglob(rootinputpath + "/*/*.obj", recursive=True):

        inputobjpath = os.path.dirname(objpath)
        #create an output folder for published models
        #simplify the obj file name else obj2gltf converter fails, use folder name without spaces
        outputobjdirname = os.path.basename(os.path.dirname(objpath))
        outputobjdirname = re.sub("\W+","", outputobjdirname) #remove all non alphabets/numbers

        outputpath = rootoutputpath + "/" + outputobjdirname
        
        if checkPaths(inputobjpath):
            #create output folder        
            if not os.path.exists(outputpath):
                os.makedirs(outputpath)

                #load template svx.json
                svx = loadSVX(rootinputpath)
            
                #generate mesh/texture lods and convert to glb
                generateLODS(objpath, outputpath, svx) 

                #create the svx file necessary for Smithsonian Voyager
                saveSVX(outputpath,svx)

                #purge input files
                purgeFiles(outputpath)
#---------------------------------------------------------------------------------------

#Input parameters:
# 1 - Root input path to OBJ files with a single PNG texture

# NOTE:
#       Looks for .svx.json in the input path folder

def main():
    paths = init()

    if not paths == False:
        publishToGLB(paths[0], paths[1])
#---------------------------------------------------------------------------------------

main()

