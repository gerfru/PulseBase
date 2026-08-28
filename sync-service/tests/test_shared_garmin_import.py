from pulsebase_garmin.client import GarminClient


def test_shared_garmin_package_exports_client():
    assert GarminClient.__name__ == "GarminClient"
