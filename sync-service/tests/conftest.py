import sys
from pathlib import Path

# sync-service/src auf den Pfad setzen damit Imports funktionieren
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


RAW_ACTIVITY_RUNNING = {
    "activityId": 12345678,
    "startTimeLocal": "2026-04-27T08:00:00",
    "activityType": {"typeKey": "running"},
    "distance": 10000.0,
    "duration": 3600.0,
    "calories": 650,
    "averageHR": 145,
    "maxHR": 172,
    "averageSpeed": 2.778,
    "averageRunningCadenceInStepsPerMinute": 174,
    "elevationGain": 42.0,
}

RAW_ACTIVITY_UNKNOWN_SPORT = {
    "activityId": 99999,
    "startTimeLocal": "2026-04-27T09:00:00",
    "activityType": {"typeKey": "lacrosse"},
}

RAW_ACTIVITY_MINIMAL = {
    "activityId": 11111,
    "startTimeLocal": "2026-04-27T10:00:00",
}

RAW_SLEEP = {
    "dailySleepDTO": {
        "id": 555,
        "sleepStartTimestampLocal": 1745704800000,
        "sleepEndTimestampLocal": 1745733600000,
        "sleepTimeSeconds": 27000,
        "deepSleepSeconds": 5400,
        "lightSleepSeconds": 12600,
        "remSleepSeconds": 7200,
        "awakeSleepSeconds": 1800,
        "sleepScores": {"overall": {"value": 78}},
    }
}

RAW_HRV = {
    "hrvSummary": {
        "lastNightAvg": 42,
        "weeklyAvg": 45,
        "status": "BALANCED",
    }
}
