#-------------------------------------------------------------------------------
# Name:        Final Project
# Purpose:
#
# Author:      Artur Wojtas
#
# Created:     09-04-2018
# Copyright:   (c) Owner 2018
# Licence:     <your licence>
#
# NOTES
# To run the script, "dataFolder" variable passed to main function has to be
# changed from default to correct path if required
# dataFolder = "C:\gisclass\GEOS456_GIS_Programming\FinalProject\FinalProject_Data"
#
#
#-------------------------------------------------------------------------------

from functools import reduce
import os
import csv
import traceback
import arcpy
import arcpy.da as da
import arcpy.sa as sa

def main(dataFolder):
    dems = "DEM_72E09\\072e09_0201_deme.dem","DEM_72E09\\072e09_0201_demw.dem"
    projectArea = "Base_72E09\\rec_park.shp"
    rivers = "Base_72E09\\river.shp"
    roads = "Base_72E09\\roads.shp"
    landcover = "Land_Cover\\landcov"
    facilities = "Oil_Gas\\facilities.shp"
    wells = "Oil_Gas\\wells.shp"

    startPt = 'AF2160553'
    endPt = '0084011408000'

    params = {"dataFolder" : dataFolder,
        "projectArea" : projectArea,
        "database" : "FinalProject.gdb",
        "dataset" : "AreaOfInterest",
        "rasterDataset" : "Rasters",
        "mosaic" : "Mosaic",
        "elev" : "Elev",
        "slope" : "Slope_cost",
        "land" : "Land_cost",
        "cost" : "Project_cost",
        'spatialReference' : "NAD 1983 UTM Zone 12N",
        "ext": "spatial"}


    setupWorkspace(params)
    createDatabase(params)

    slope = obtainSlope(params, dems)
    land = obtainLandCover(params, landcover)
    rivers_buffered = obtainMultiBuffer(params, rivers, projectArea , [20, 200], [[20, 3], [200, 2]], 1)
    roads_buffered = obtainMultiBuffer(params, roads, projectArea, [20, 200], [[20, 1], [200, 2]], 3)

    costRaster = obtainCostRaster(params, slope, land, rivers_buffered, roads_buffered)

    start = selectFeature(params, facilities, "UFI = 'AF2160553'")
    finish = selectFeature(params, wells, "UWID = '0084011408000'")

    #optimalPath = obtainPath(params, [start, finish], os.path.join(params["database"], params["cost"]))
    optimalPath = obtainPath(params, [start, finish], costRaster)

    arcpy.CheckInExtension(params["ext"])


def errorMessage():
    tb = sys.exc_info( )[2]
    tbinfo = traceback.format_tb( tb )[0]
    pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError \
    Info:\n" + str( sys.exc_info( )[1] )
    #msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages( 2 ) + "\n"
    #arcpy.AddError( pymsg )
    #arcpy.AddError( msgs )
    print(pymsg)
    #print(msgs)


def setupWorkspace(params):
    '''
    Set up workspoace and checkout spatial extension
    '''
    print("Setting up workspace")
    workspace = params["dataFolder"] #os.path.join(param["dataFolder"], param["database"])

    arcpy.env.workspace = workspace
    arcpy.env.scratchWorkspace = workspace #os.path.join(param["dataFolder"], param["database"])
    arcpy.env.overwriteOutput = True

    print arcpy.ProductInfo()
    print arcpy.CheckProduct(arcpy.ProductInfo())

    #Checkout spatial extension
    print "Spatial Ext: {0}".format(arcpy.CheckExtension(params["ext"]))
    if arcpy.CheckExtension(params["ext"]) == "Available":
        print ("Checking out extension: spatial")
        arcpy.CheckOutExtension(params["ext"])
    else:
        raise Exception("No spatial extansion avilable")

    print("")


def wait(delay):
    '''
    Delay function in seconds
    '''
    for i in reversed(range(1,4)):
        print("Wait {0} sec".format(i))
        time.sleep(1)
    print("")

def createDatabase(params):
    '''
    Create database for analysis and processing

    '''
    print("Creating database...")
    try:
        database = os.path.join(params["dataFolder"], params["database"])
        if arcpy.Exists(database):
            print("Delete existing database: {0}\n".format(params["database"]))
            arcpy.Delete_management(params["database"])
            print(arcpy.GetMessages())
            print("")

        #Create databse for the project
        arcpy.CreateFileGDB_management(params["dataFolder"], params["database"])
        print(arcpy.GetMessages())
        print("")
        wait(2)

        #Create dataset with common spatial reference
        spatialRef = arcpy.SpatialReference(26912)
        #spatialRef = arcpy.SpatialReference(params["spatialReference"])

        arcpy.CreateFeatureDataset_management(database, params["dataset"], spatialRef )
        print(arcpy.GetMessages())
        print("")
        wait(2)

        ###Did not used this
        '''
        arcpy.CreateRasterDataset_management (database, params["rasterDataset"], "", "16_BIT_SIGNED", spatialRef, "1")
        print(arcpy.GetMessages())
        print("")
        #Required before starting adding date to database
        wait(2)
        '''

        dataset =  os.path.join(params["database"], params["dataset"])
        result = arcpy.FeatureClassToGeodatabase_conversion(params["projectArea"], dataset)
        print(arcpy.GetMessages())
        print("")
    except:
        errorMessage()


def wait(delay):
    '''
    Delay function in seconds
    '''
    for i in reversed(range(1,delay+1)):
        print("Wait {0} sec".format(i))
        time.sleep(1)
    print("")


def selectFeature(params, inputFeature, attribute):
    '''
    Select feature by attribute
    '''
    print("Selecting feature... " + attribute )
    try:
        name = inputFeature.split("\\")[1].split(".")[0]
        outputFeature = os.path.join(os.path.join(params["database"], params["dataset"]),name)
        selection = arcpy.Select_analysis(inputFeature, outputFeature, attribute)
        print(arcpy.GetMessages())
        print("")
        return outputFeature
    except Exception as e:
        print(e)


def describeRaster(name):
    '''
    Describe raster file
    '''
    try:
        desc = arcpy.Describe(name)
        print("Data type: {0}".format(desc.dataType))
        print("Cell Size: {0} x {1}".format(desc.meanCellWidth, desc.meanCellHeight))
        spetialRef =  desc.spatialReference
        if spetialRef:
            print("Spetial Reference: {0}".format(spetialRef.name))
            print("Units: {0}".format(spetialRef.linearUnitName))
            print("Meters per Unit: {0}".format(spetialRef.metersPerUnit))
    except Exception as e:
        print(e)

def obtainSlope(params, files):
    '''
    Obtain slope from elevation mosaic, and reclassify to cost values
    '''
    print("Calculate slope...")
    try:
        spatialRef = arcpy.SpatialReference(26912)
        #arcpy.Mosaic_management(files, params["mosaic"], dem, "MEAN")
        arcpy.MosaicToNewRaster_management(files, params["database"], params["mosaic"], spatialRef, "16_BIT_SIGNED", "", "1")
        print(arcpy.GetMessages())
        print("")
        ##arcpy.MakeFeatureLayer_management(files[0], layer)

        name = params["projectArea"].split("\\")[1].split(".")[0]
        projectArea = os.path.join(os.path.join(params["database"], params["dataset"]), name)
        elev = sa.ExtractByMask(os.path.join(params["database"], params["mosaic"]), projectArea)
        print(arcpy.GetMessages())
        print("")

        elev_resample = os.path.join(os.path.join(params["dataFolder"], params["database"]), params["elev"])
        arcpy.Resample_management (elev, elev_resample, "25")
        print(arcpy.GetMessages())
        print("")

        #elev.save(params["elev"])
        #print(arcpy.GetMessages())
        #print("")

        slope = sa.Slope(elev_resample)
        print(arcpy.GetMessages())
        print("")

        int_slope = sa.Int(slope)
        print(arcpy.GetMessages())
        print("")

        #int_slope.save(params["slope"])
        #print(arcpy.GetMessages())
        #print("")

        min = int_slope.minimum
        max = int_slope.maximum

        remap = sa.RemapRange([[min, 1, 1], [2, 8, 2], [9, max, 3]])
        int_slope_reclass = sa.Reclassify(int_slope, "Value", remap)

        tempWorkspace = arcpy.env.workspace
        arcpy.env.workspace = os.path.join(params["dataFolder"], params["database"])
        int_slope_reclass.save(params["slope"])

        arcpy.env.workspace = tempWorkspace
        return int_slope_reclass
    except:
        errorMessage()


def obtainLandCover(params, land):
    '''
    Reclassify land cover to cost value
    '''
    print("Obtain land cover...")

    '''
    classification ={ "Cropland" : 1,
        "Forage" : 2,
        "Grassland" : 3,
        "Shrubs" : 4,
        "Trees" : 5,
        "Water" : 7}

    classificationScale ={ "Cropland" : 3,
        "Forage" : 1,
        "Grassland" : 1,
        "Shrubs" : 2,
        "Trees" : 2,
        "Water" : 3}
    '''

    try:
        remap = sa.RemapValue([[1, 3], [2, 1], [3, 1], [4, 2], [5, 2], [7, 3]])
        output = sa.Reclassify(land, "Value", remap)
        print(arcpy.GetMessages())
        print("")

        tempWorkspace = arcpy.env.workspace
        arcpy.env.workspace = os.path.join(os.path.join(params["dataFolder"], params["database"]))
        output.save(params["land"])
        print(arcpy.GetMessages())
        print("")

        arcpy.env.workspace = tempWorkspace
        return output
    except:
        errorMessage()


def obtainMultiBuffer(params, feature, area, distances, classification, fillValue):
    '''
    Create multibuffer specified with distances value, convert it to raster, and
    reclassify it with cost values
    '''
    print("Clipping and Bufferig feature... " + feature)
    name = feature.split("\\")[1].split(".")[0]

    clipped = os.path.join(os.path.join(params["database"], params["dataset"]), "Clipped_" + name)
    buffer = os.path.join(os.path.join(params["database"], params["dataset"]), "multiBuffered_" + name)
    bufferRaster = os.path.join(params["database"], "MultiBufferedRaster_" + name)
    remapBufferRaster = ("" + name + "_cost")
    try:
        arcpy.Clip_analysis(feature, area, clipped)
        print(arcpy.GetMessages())
        print("")
        arcpy.MultipleRingBuffer_analysis(clipped, buffer, distances,
            "meters", "", "ALL")
        print(arcpy.GetMessages())
        print("")

        #PolygonToRaster_conversion (in_features, value_field, out_rasterdataset, {cell_assignment}, {priority_field}, {cellsize})
        arcpy.PolygonToRaster_conversion(buffer, "distance", bufferRaster, "", "", "25")
        print(arcpy.GetMessages())
        print("")

        raster = arcpy.Raster(bufferRaster)
        remap = sa.RemapValue(classification)
        outputRaster = sa.Reclassify(raster, "Value", remap)
        print(arcpy.GetMessages())
        print("")

        raster = sa.Con(sa.IsNull(outputRaster), fillValue, outputRaster)
        print(arcpy.GetMessages())
        print("")

        rasterExtract = sa.ExtractByMask(raster, area)
        print(arcpy.GetMessages())
        print("")

        tempWorkspace = arcpy.env.workspace
        arcpy.env.workspace = os.path.join(os.path.join(params["dataFolder"], params["database"]))
        rasterExtract.save(remapBufferRaster)

        print(arcpy.GetMessages())
        print("")
        arcpy.env.workspace = tempWorkspace

        return rasterExtract
    except Exception as e:
        errorMessage()


def obtainCostRaster(params, *rasters):
    '''
    Calculate total cost for all rasters
    '''
    print("Obtaining cost raster...")
    try:
        costRaster = reduce(lambda x, y: x + y, rasters)

        tempWorkspace = arcpy.env.workspace
        arcpy.env.workspace = os.path.join(os.path.join(params["dataFolder"], params["database"]))
        costRaster.save(params["cost"])
        print(arcpy.GetMessages())
        print("")
        arcpy.env.workspace = tempWorkspace

        return costRaster
    except:
        errorMessage()


def obtainPath(params, locations, cost):
    '''
    Obtain optimal path between two locations based on cost
    '''
    try:
        #Create feature class with start and finish locations for cost analysis
        coords = getLocation(locations)
        featurePts = createPointFeature(params, coords)

        featurePtsPath = os.path.join(os.path.join(params["database"], params["dataset"]), featurePts)
        outputPathCost = os.path.join(os.path.join(params["database"], params["dataset"]), "Path_Cost")

        sa.CostConnectivity(featurePtsPath, cost, outputPathCost)
        print(arcpy.GetMessages())
        print("")

    except:
        errorMessage()

def getLocation(features):
    '''
    Obtain coordinates from features
    '''
    coords = []
    for feature in features:
        for row in arcpy.da.SearchCursor(feature, ["SHAPE@"]):
            # Print the current multipoint's ID
            #
            print("Feature {}:".format(row[0]))
            # For each point in the multipoint feature,
            #  print the x,y coordinates
            for pnt in row[0]:
                print("{}, {}".format(pnt.X, pnt.Y))
                coords.append((pnt.X, pnt.Y))
                print(coords)
    return coords


def createPointFeature(params, coords):
    '''
    Create point feaature class from coordinates
    '''
    locations = "Locations"
    try:
        tempWorkspace = arcpy.env.workspace
        arcpy.env.workspace = os.path.join(params["dataFolder"], params["database"])

        arcpy.CreateFeatureclass_management(params["dataset"], locations, "POINT")
        print(arcpy.GetMessages())
        print("")

        cursor = arcpy.da.InsertCursor(os.path.join(params["dataset"], locations), ("SHAPE@"))
        for row in coords:
            print(row)
            point = arcpy.Point(row[0], row[1])
            ptGeometry = arcpy.PointGeometry(point)

            cursor.insertRow(ptGeometry)

        del(cursor)
        arcpy.env.workspace = tempWorkspace

        return locations
    except:
        errorMessage()


if __name__ == "__main__":
    print("Starting {0}\n".format(__name__))

    dataFolder = "C:\gisclass\GEOS456_GIS_Programming\FinalProject\FinalProject_Data"
    main(dataFolder)

    print("\nFinished")

else:
    print("Importing {0}".format(__name__))