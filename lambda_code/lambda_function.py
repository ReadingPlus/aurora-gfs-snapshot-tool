#!/usr/bin/env python3

from datetime import datetime, timezone, date
import os
import sys
import boto3
import logging
import json

#setup global logger
logger = logging.getLogger("SnapTool")
#set log level
LOGLEVEL = os.environ['LogLevel'].strip()
logger.setLevel(LOGLEVEL.upper())
logging.getLogger("botocore").setLevel(logging.ERROR)

#setup global RDS client
rds = boto3.client("rds")

#rds snapshot tool tag name
toolTagKey="SnapTool"


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def startTool(timeNow):
    dbClusters=[]
    if os.environ['DatabaseNames'] == "ALL":
        resp=rds.describe_db_clusters()
        for db in resp['DBClusters']:
            dbClusters.append(db['DBClusterIdentifier'])
    else:
        dbClusters=os.environ['DatabaseNames'].split(",")
    #make all lowercase
    dbClusters=[x.lower() for x in dbClusters]

    verifyClusters(dbClusters)

    backupConfig=[]
    backupConfig.append({
        "timePeriod": "yearly",
        "retention": int(os.environ['YearlyRetention'])
    })
    backupConfig.append({
        "timePeriod": "monthly",
        "retention": int(os.environ['MonthlyRetention'])
    })
    backupConfig.append({
        "timePeriod": "weekly",
        "retention": int(os.environ['WeeklyRetention'])
    })

    for db in dbClusters:
        logger.info("Analyzing snapshot status for DB:" + db)

        newSnapPeriod = []
        snapsToDelete = {}

        for period in backupConfig:
            if(period['retention']> 0):
                if (validBackupTime(timeNow, period['timePeriod'])):
                    newSnapPeriod.append(period['timePeriod'])
                    #check if there are snaps to delete keeping in mind we will be creating a new one soon
                    snapsToDelete[period['timePeriod']] = checkDeleteNeeded(db, period['timePeriod'], period['retention']-1)
                else:
                    #check if there are snaps to delete
                    snapsToDelete[period['timePeriod']] = checkDeleteNeeded(db, period['timePeriod'], period['retention'])
            else:
                logger.info("No " + period['timePeriod'] + " retention specified.")
                # delete any snaps if present
                deleteAllSnaps(db, period['timePeriod'])


        if(newSnapPeriod != []):
            createSnap(db, newSnapPeriod)
        else:
            logger.info("No snapshot needed today.")

        #delete snaps if needed
        for timePeriod in snapsToDelete.keys():
            for snap in snapsToDelete[timePeriod]:
                deleteSnap(snap, timePeriod)

def validBackupTime(timeNow, timePeriod):
    backupDate = int(os.environ['BackupDate'])
    backupMonth = os.environ['BackupMonth']
    weeklyBackupDay = os.environ['WeeklyBackupDay']

    logger.debug("Checking if " + timePeriod + " retention policy is satisfied.")

    if (timePeriod == "yearly"):
        if(timeNow.day == backupDate and timeNow.strftime("%B") == backupMonth):
            logger.debug("Backup date matches specifications")
            return True
    elif (timePeriod == "monthly"):
        if (timeNow.day == backupDate):
            logger.debug("Backup date matches specifications")
            return True
    elif (timePeriod == "weekly"):
        if(timeNow.strftime("%A") ==weeklyBackupDay):
            logger.debug("Backup date matches specifications")
            return True
    else:
        logger.error("Invalid time period.  Exiting")
        sys.exit(1)

    logger.debug("Backup date does not match specifications. Skipping snapshot")
    return False

def checkDeleteNeeded(db, timePeriod, retention):
    snaps=getSnaps(db,timePeriod)

    if(snaps is not None and len(snaps)>=retention):
        return snaps[:-retention]
    else:
        return []

def deleteAllSnaps(db,timePeriod):

    snaps = getSnaps(db, timePeriod)

    if(snaps is not None):
        logger.info("Removing any old " + timePeriod + " snapshots.")
        for snap in snaps:
            deleteSnap(snap, timePeriod)

def getSnaps(db, timePeriod):
    validSnaps = []
    if ("dateSimulationDebugFile" in os.environ):
        # snapshot info is stored in local file for debugging
        snapStore = {}
        try:
            with open(os.environ['dateSimulationDebugFile'], 'r') as fp:
                snapStore = json.load(fp)
        except Exception:
            logger.exception("Failed to load snapshot store file.  Failing")
            sys.exit(1)

        for snap in snapStore[db]:
            if (timePeriod in snap['Tag']):
                # time period matches

                # convert date strings to datetime objects
                snap['SnapshotCreateTime'] = datetime.strptime(snap['SnapshotCreateTime'],
                                                               "%Y-%m-%dT%H:%M:%S.%f+00:00").replace(tzinfo=timezone.utc)
                validSnaps.append(snap)
    else:
        snaps = rds.describe_db_cluster_snapshots(
            DBClusterIdentifier=db,
            SnapshotType="manual"
        )

        for s in snaps['DBClusterSnapshots']:
            tags = rds.list_tags_for_resource(ResourceName=s['DBClusterSnapshotArn'])
            for t in tags['TagList']:
                if t['Key'] == toolTagKey and timePeriod in t['Value']:
                    validSnaps.append(s)

    if (len(validSnaps) > 0):
        # sort snaps by date
        sortedArray = sorted(
            validSnaps,
            key=lambda x: x['SnapshotCreateTime'],
            reverse=False
        )
        return sortedArray
    else:
        return None

def createSnap(db, tags):
    logger.info("Creating snapshot on DB:" + db + " with tags:" + str(tags))

    if ("dateSimulationDebugFile" in os.environ):
        # snapshot info is stored in local file for debugging

        # get simulated date from env var
        simDate = datetime.strptime(os.environ['debugDate'],
                                                       "%Y-%m-%dT%H:%M:%S.%f+00:00").replace(tzinfo=timezone.utc)

        snap = {
            "Tag": " ".join(tags),
            "SnapshotCreateTime": simDate,
            "DBClusterIdentifier" : db
        }

        try:
            with open(os.environ['dateSimulationDebugFile'], 'r') as json_data:
                snapJson= json.load(json_data)

            snapJson[db].append(snap)

            with open(os.environ['dateSimulationDebugFile'], 'w') as json_data:
                json.dump(snapJson, json_data, default=json_serial)
        except Exception:
            logger.exception("Failed to read or write snapshot store file.  Failing")
            sys.exit(1)
    else:
        snapshotName=db + "-" + datetime.now().strftime('%Y-%m-%d')
        rds.create_db_cluster_snapshot(
            DBClusterSnapshotIdentifier=snapshotName,
            DBClusterIdentifier=db,
            Tags=[
                {
                    "Key": toolTagKey,
                    "Value": " ".join(tags)
                }
            ])

def deleteSnap(snapToDelete, timePeriod):
    logger.debug("Received a delete request for the " + timePeriod + " time period.")

    if ("dateSimulationDebugFile" in os.environ):
        # snapshot info is stored in local file for debugging

        #read local file
        snapJson={}
        try:
            with open(os.environ['dateSimulationDebugFile'], 'r') as json_data:
                snapJson = json.load(json_data)
        except Exception:
            logger.exception("Failed to read snapshot store file.  Failing")
            sys.exit(1)

        #check all snaps to see if date matches
        newSnapList=[]
        for snap in snapJson[snapToDelete['DBClusterIdentifier']]:
            # convert date strings to datetime objects
            snap['SnapshotCreateTime'] = datetime.strptime(snap['SnapshotCreateTime'], "%Y-%m-%dT%H:%M:%S.%f+00:00").replace(tzinfo=timezone.utc)

            if (snap['SnapshotCreateTime'].date() == snapToDelete['SnapshotCreateTime'].date()):
                #found snap with correct date
                tags = snap['Tag'].split(" ")
                if(len(tags) ==1 and tags[0]==timePeriod):
                    #we can delete it
                    logger.info("Deleting " + timePeriod + " snap from test file")
                    continue
                else:
                    #update tag to remove time period
                    tags.remove(timePeriod)
                    snap['Tag']=" ".join(tags)

            #if we are NOT deleting the snap we add its info to a new list
            newSnapList.append(snap)

        snapJson[snapToDelete['DBClusterIdentifier']]=newSnapList

        try:
            #write to file
            with open(os.environ['dateSimulationDebugFile'], 'w') as json_data:
                json.dump(snapJson, json_data, default=json_serial)
        except Exception:
            logger.exception("Failed to write snapshot store file.  Failing")
            sys.exit(1)
    else:
        #using RDS information for snapshots

        # check tags on snapshot
        tags = rds.list_tags_for_resource(ResourceName=snapToDelete['DBClusterSnapshotArn'])
        for t in tags['TagList']:
            if t['Key'] == toolTagKey:
                tags = t['Value'].split(" ")
                if (len(tags) == 1 and tags[0] == timePeriod):
                    # if the time period specified is the only remaining timeperiod we can delete it
                    logger.info("Deleting snapshot: " + snapToDelete['DBClusterSnapshotIdentifier'] + " from RDS.")
                    #delete from RDS
                    rds.delete_db_cluster_snapshot(DBClusterSnapshotIdentifier=snapToDelete['DBClusterSnapshotArn'])
                else:
                    # update tag to remove time period
                    logger.info("Removing time period tag:" + timePeriod + " from snapshot:" + snapToDelete['DBClusterSnapshotIdentifier'])
                    tags.remove(timePeriod)
                    #rds update tag on snapshot
                    t['Value']= " ".join(tags)
                    rds.add_tags_to_resource(ResourceName=snapToDelete['DBClusterSnapshotArn'], Tags=[t])
                break

def verifyClusters(dbClusters):
    existingDBClusters=[d['DBClusterIdentifier'] for d in rds.describe_db_clusters()['DBClusters']]

    for db in dbClusters:
        logger.debug("Checking if DB:" + db + " is an existing Aurora Cluster.")

        if(db in existingDBClusters):
            logger.debug("DB:" + db + " is a valid cluster.")
        else:
            logger.error("DB:" + db + " is NOT a valid cluster.  Failing")
            sys.exit(1)

def lambda_handler(event, context):
    logger.info("Starting Aurora Snapshot Generator tool")

    logger.debug("Environment Variables:")
    for key in os.environ:
        logger.debug("Found {}={}".format(key, os.environ[key]))

    logger.debug("Checking for required env vars.")
    requiredEnvVars = ['DatabaseNames', 'WeeklyRetention', 'MonthlyRetention', 'YearlyRetention','WeeklyBackupDay', 'BackupDate', 'BackupMonth']
    for r in requiredEnvVars:
        if r not in os.environ.keys():
            logger.error("Required variable:" + r + " not found.  Exiting.")
            sys.exit(1)

    timeNow=datetime.now(timezone.utc)
    logger.debug("Month:" + str(timeNow.strftime("%B")) + " Day:" + str(timeNow.day) + " DOW:" + str(timeNow.strftime("%A")))

    startTool(timeNow)

    logger.info("End of Aurora Snapshot Generator tool")

