import uuid
import json
import os
import datetime
import shutil
import graphql #Local module file
import pytz
from pytz import timezone
import inspect

#See https://stackoverflow.com/questions/50499/how-do-i-get-the-path-and-name-of-the-file-that-is-currently-executing
baseDir= os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

with open(os.path.join(baseDir, '..', 'config.json')) as config_file:
    config = json.load(config_file)

# Where we expect to find test result files to process
workDir=os.path.join(config['rootDir'],config['paths']['testPing'])

#Set localtimezone
utc = pytz.utc
mytz = timezone(config['tz'])

# Where to put the files that have been processed
processedFilesDir = os.path.join(workDir,config['paths']['processedFiles'])
if not os.path.isdir(processedFilesDir):
    os.mkdir(processedFilesDir)

#Pick up the ping results directory from the dictionary we created above
# and use it to go get all the ping result files in that directory
files = [ f for f in os.listdir(workDir) if os.path.isfile(os.path.join(workDir, f)) ]

#Now work through those results, assemble batches of _batchSize_ results and then post each batch
# AppSync supports batches of 1..25
batchSize = 20

fileCount = 0
batch = []
batchFiles = []
processedFiles = []

for file in files:
  file = os.path.join(workDir, file)

  with open(file) as infile:
    try:
      #Extract the json as json dictionary/object from the file
      payload = json.load(infile)
      payload['failed'] = False

    except ValueError:
      #No JSON in file because ping failed
      payload = {}
      payload['failed'] = True

    #TypeError is more portable than JSONDecodeError
    # https://stackoverflow.com/questions/44714046/python3-unable-to-import-jsondecodeerror-from-json-decoder
    except TypeError:
      print('Not a processable file:\t', file)
    
    #Earlier iterations of the ping gathering code 
    # didn't capture the timestamp as part of the payload
    # the following code detects this and 
    # adds it to the payload from the filename

    #See https://stackoverflow.com/questions/1602934/check-if-a-given-key-already-exists-in-a-dictionary
    #if you'd like to understand the following test
    if not 'timestamp' in payload:
      fn_plus_ext = os.path.basename(file)
      fn_wo_ext = os.path.splitext(fn_plus_ext)[0]
      #date_time_str = '2018-06-29 17:08:00'
      date_time_obj = datetime.datetime.strptime(fn_wo_ext, '%Y%m%d-%H%M%S')
      date_time_obj = mytz.localize(date_time_obj)
      date_time_obj = date_time_obj.astimezone().isoformat()
      payload['datetime'] = date_time_obj

    #Add a UUID
    payload['id'] = str(uuid.uuid4())

    #Add an approximate location as set up by user in config
    payload['countryCode'] = config['countryCode']
    payload['postalCode'] = config['postalCode']
    
    if batchSize == 1:
      #Post individual results
      result = graphql.createPing(payload)
      if result != None:
        #Add the file to the processed list
        processedFiles.append(file)
    else:
      #Add the payload to the batch
      batch.append(payload)
      batchFiles.append(file)
      fileCount = fileCount + 1

      #If we have _batchSize_ results, post the batch
      #TODO Need to add "OR there are no more source files left"
      if fileCount % batchSize == 0:
        result = graphql.batchCreatePing(batch)    
        if result != None:
          processedFiles.extend(batchFiles)
        batch = []
        batchFiles = []


#Move the file to the processed list
for bf in processedFiles:
  try:
    #TODO Change to delete by config
    shutil.move(bf, processedFilesDir)
  except TypeError:
    print('Not a moveable file:\t', bf)