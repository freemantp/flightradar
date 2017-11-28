import requests
import json, time
import collections

payload = '{"req":"getStats","data":{"statsType":"counters"}}'

secondsInterval = 1
oldValue = 0

buf = collections.deque(maxlen=5)


def mean(numbers):
    return float(sum(numbers)) / max(len(numbers), 1)

maxV = 0;
minV = 99999999;

while(True):
    r = requests.post('http://192.168.0.40:8081/json', data = payload)
    j = json.loads(r.text)

    numMessages = int(j['stats']['counters']['TOTAL_MSG'])
    numMessages - oldValue
    msgPerSec = (numMessages - oldValue) / secondsInterval
    
    if oldValue > 0:
        buf.append(msgPerSec)
        daMean = mean(buf)

        if daMean > maxV: maxV = daMean
        if daMean < minV: minV = daMean

        print("%d msg/sec (%d avg, %d min, %d max)" % (daMean, len(buf),minV,maxV) )

    oldValue = numMessages



    

    
    time.sleep(secondsInterval)