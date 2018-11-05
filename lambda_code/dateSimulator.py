#!/usr/bin/env python3

from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import os
import logging
import json

#set up logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("/tmp/date.log")
FORMAT = '%(asctime)-15s | %(levelname)s | %(message)s'
formatter = logging.Formatter(FORMAT)
fh.setFormatter(formatter)
logger.addHandler(fh)

#set environment variables for local run
os.environ['DatabaseNames'] = "" #input a valid database here
os.environ['LogLevel'] = "DEBUG"
os.environ['MonthlyRetention'] = str(2)
os.environ['WeeklyBackupDay'] = "Sunday"
os.environ['BackupDate'] =str(1)
os.environ['BackupMonth'] ="January"
os.environ['WeeklyRetention'] = str(7)
os.environ['YearlyRetention'] = str(2)

from lambda_function import startTool

if __name__ == "__main__":
    logger.info("Simulating range of dates for snapshot tool.")

    snapStoreFile="snapStore.json"

    jsonTemplate={}
    for db in os.environ['DatabaseNames'].split(","):
        jsonTemplate[db]=[]

    with open(snapStoreFile, 'w') as fp:
        json.dump(jsonTemplate, fp)

    os.environ['dateSimulationDebugFile']=snapStoreFile

    startDate=datetime.now(timezone.utc)
    endDate = startDate + relativedelta(years=2)

    delta = endDate - startDate

    for i in range(delta.days + 1):
        curDate=startDate + timedelta(i)
        logger.info("I: " + str(i) + " Date:" +str(curDate.date()) )
        os.environ['debugDate']=curDate.isoformat()

        #Change parameter after installation
        if(str(curDate.date()) == "2019-01-19"):
            os.environ['WeeklyRetention'] = str(2)

        startTool(curDate)
        with open(snapStoreFile, 'r') as fp:
            snapJson = json.load(fp)
            logger.debug(json.dumps(snapJson, indent=3))

    #clean up
    os.remove(snapStoreFile)