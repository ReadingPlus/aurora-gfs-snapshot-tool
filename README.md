# GFS Snapshot Tool
This repository holds the code for an AWS Aurora snapshot tool.  It utilizes a grandfather-father-son backup scheme to preserve snapshots.

## Backup Scheme
This tool utilizes a grandfather-father-son backup strategy to store its backups([Wiki](https://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son)).  The tool operates with three tiers of backups: Weekly, Monthly, and Yearly.  Daily backup functionality is provided natively by AWS([Docs](https://aws.amazon.com/rds/faqs/#automated-backups-database-snapshots)).  Using this strategy allows us to maintain backups for a longer period of time without holding onto too many snapshots at once.  The most amount of snapshots the tool will ever have at one time is equal to the sum of all your retention policies(Details in the Parameters secion) 

## How it works
This tool uses Python Code running on AWS Lambda to create, delete and maintain AWS Aurora Snapshots.  The tool runs once a day based on a Cloudwatch Event Rule.  The snapshots are managed based on parameters specified at installation time.  When snapshots are created they are tagged with the "time period" they are intended for.  Snapshots can share time periods when these periods overlap, reducing snapshot footprint.  When a snapshot has gone past its specified retention period(and is the only time period using it) it is deleted.  
     
##Local Testing
To aid in logic debugging and long term assesment of the tool a [Date Simulator Script](lambda_code/dateSimulator.py) is provided.  The script simulates operating the tool over a long period of time.  You can use this tool to validate proper operation of the tool.

## Installation/Configuration
To install the gfs-snapshot-tool we need to perform two steps:
1. Upload the Python Code to AWS S3.
2. Deploy the Cloudformation template.

### Upload Python Code  
####Mac/Linux installation
If you are utilizing a mac or linux workstation we can install with the provided [deployTool.sh](deployTool.sh) script.  This tool automates the upload of the code to S3 and prepares the Cloudformation template for you.  Before you use it please make sure you have the following in place:
- AWS CLI tool installed with permissions to S3 and Cloudformation
- An AWS S3 bucket

When the above are in place you can use the script like so:
```
sh deployTool.sh <your-bucket-name> <optional-region-name>
```

If successful the script will output a cloudformation link.  You can then open that Cloudformation link in your browser to complete installation.

####Windows installation
To upload the code from a Windows workstation you will have to create the code archive manually.  To do this please follow these steps:
1. Zip up the [lamda_code](lambda_code) folder
2. Using the AWS S3 console upload that zip file to a S3 bucket you control.
3. Edit the [Cloudformation Template](cloudformation/template.json) to specify the location(S3 bucket) where you uploaded your code.  Find the **"code"** property in the **"lambdaFunction"** resource and edit it to look like this:
         ```
"Code": {
        "S3Bucket": "<your-bucket-name>",
        "S3Key": "<name-of-file>"
},
        ```
4. Using the AWS Cloudformation console create a new stack with the newly edited [template.json](cloudformation/template.json) 

### Deploy Cloudformation Template
To finalize the installation of the tool you will need to create the Cloudformation stack.  Using either method above you should now be looking at the Cloudformation console.  The following parameters are available:

* **DatabaseNames** - Comma separated list of Database Clusters to backup. Use All to backup all clusters(in region)
* **BackupTime** - Daily hour to run backup script. Time is in UTC. Default is 0(Midnight)
* **LogLevel** - Log level for Lambda functions (DEBUG, INFO, ERROR are valid values).
* **Email** - Email to use for Alarm Alerting.  Email specified will receive an alert if the script has an error.
* **WeeklyRetention** - Retention time for weekly backups. This value determines how many weeks to keep weekly snapshots. The default value is 4. 0 Turns the weekly backups off.
* **WeeklyBackupDay** - Day of the week to take weekly snapshot. Default is Sunday. If WeeklyRetention is set to 0 this is ignored.
* **MonthlyRetention** - Retention time for monthly backups. This value determines how many months to keep monthly snapshots. The default value is 4. 0 turns the monthly backups off.
* **BackupDate** - Day of the month to take Monthly and/or Yearly Backups. Default is 1. Allowed values are 1-28.
* **YearlyRetention** - Retention time for yearly backups. This value determines how many years to keep yearly snapshots. The default value is 2. 0 turns the yearly backups off.
* **BackupMonth** - Month of the year to take the yearly snapshot. Combined with BackupDate to determine when yearly backups are taken. Ignored if YearlyRetention is set to 0. Default is January.

After inputting all of the above parameters you can create the stack and the tool will be up and running!

## Updating
To update the configuration of the tool you can simply update the cloudformation stack to set the desired parameter properly.   

## Authors

* **Jonathan Russo** - [jonathan-russo](https://github.com/jonathan-russo)

## License

This project is licensed under the terms of the MIT license.  [License](LICENSE.txt)