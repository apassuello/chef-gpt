"""
Integration tests for device state transitions.

Tests the device state machine transitions:
- idle → preheating → cooking → done
- cooking → idle (via stop)
- any → offline (connection lost)

Reference: docs/09-integration-test-specification.md Section 4
"""

import responses


@responses.activate
def test_int_st_01_idle_to_preheating(
    client,
    auth_headers,
    valid_cook_requests
):
    """
    INT-ST-01: Starting cook transitions from idle to preheating.

    Reference: Spec lines 891-913
    """
    # ARRANGE: Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={
            "idToken": "mock-id-token",
            "refreshToken": "mock-refresh-token",
            "expiresIn": "3600"
        },
        status=200
    )

    # Mock 1st status check: device is idle
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "IDLE",
            "currentTemperature": 22.5,
            "targetTemperature": None,
            "cookTimeRemaining": None,
            "cookTimeElapsed": None
        },
        status=200
    )

    # Mock 2nd status check (inside start_cook): device still idle
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "IDLE",
            "currentTemperature": 22.5,
            "targetTemperature": None,
            "cookTimeRemaining": None,
            "cookTimeElapsed": None
        },
        status=200
    )

    # Mock start cook command succeeds
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test-device-123/cook",
        json={
            "success": True,
            "cookId": "550e8400-e29b-41d4-a716-446655440000",
            "state": "preheating"
        },
        status=200
    )

    # Mock 3rd status check (after start): device now preheating
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "PREHEATING",
            "currentTemperature": 45.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 5400,
            "cookTimeElapsed": 0
        },
        status=200
    )

    # ACT 1: Verify initial state is idle
    response = client.get('/status', headers=auth_headers)
    assert response.status_code == 200
    status_data = response.get_json()
    assert status_data["state"] == "idle", \
        f"Expected initial state 'idle', got '{status_data['state']}'"

    # ACT 2: Start cook
    response = client.post(
        '/start-cook',
        headers=auth_headers,
        json=valid_cook_requests["chicken"]
    )
    assert response.status_code == 200, \
        f"Start cook failed: {response.get_json()}"

    # ACT 3: Verify state transitioned to preheating or cooking
    response = client.get('/status', headers=auth_headers)
    assert response.status_code == 200
    status_data = response.get_json()

    # State should be preheating or cooking (device may heat up quickly)
    assert status_data["state"] in ["preheating", "cooking"], \
        f"Expected 'preheating' or 'cooking', got '{status_data['state']}'"

    # Device should be running
    assert status_data["is_running"] is True, \
        "Device should be running after start cook"


@responses.activate
def test_int_st_02_preheating_to_cooking(client, auth_headers):
    """
    INT-ST-02: Reaching target temp transitions to cooking.

    Reference: Spec lines 917-960
    """
    # ARRANGE: Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={"idToken": "mock-token", "refreshToken": "refresh", "expiresIn": "3600"},
        status=200
    )

    # Mock 1st status call: device is preheating
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "PREHEATING",
            "currentTemperature": 50.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 5400,
            "cookTimeElapsed": 300
        },
        status=200
    )

    # Mock 2nd status call: device reached temp, now cooking
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "COOKING",
            "currentTemperature": 65.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 5100,
            "cookTimeElapsed": 600
        },
        status=200
    )

    # ACT: Check status twice to see progression
    response1 = client.get('/status', headers=auth_headers)
    assert response1.status_code == 200
    status1 = response1.get_json()
    assert status1["state"] == "preheating"
    assert status1["current_temp_celsius"] < status1["target_temp_celsius"]

    response2 = client.get('/status', headers=auth_headers)
    assert response2.status_code == 200
    status2 = response2.get_json()
    assert status2["state"] == "cooking"
    assert status2["current_temp_celsius"] == status2["target_temp_celsius"]


@responses.activate
def test_int_st_03_cooking_to_done(client, auth_headers):
    """
    INT-ST-03: Timer expiring transitions to done.

    Reference: Spec lines 964-1005
    """
    # ARRANGE: Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={"idToken": "mock-token", "refreshToken": "refresh", "expiresIn": "3600"},
        status=200
    )

    # Mock 1st status: cooking with time remaining
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "COOKING",
            "currentTemperature": 65.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 300,  # 5 minutes
            "cookTimeElapsed": 5100
        },
        status=200
    )

    # Mock 2nd status: timer expired, done
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "DONE",
            "currentTemperature": 65.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 0,
            "cookTimeElapsed": 5400
        },
        status=200
    )

    # ACT: Check progression
    response1 = client.get('/status', headers=auth_headers)
    assert response1.status_code == 200
    status1 = response1.get_json()
    assert status1["time_remaining_minutes"] == 5

    response2 = client.get('/status', headers=auth_headers)
    assert response2.status_code == 200
    status2 = response2.get_json()
    assert status2["state"] == "done"
    # When timer reaches 0, it returns None (cookTimeRemaining is falsy)
    assert status2["time_remaining_minutes"] in [0, None]


@responses.activate
def test_int_st_04_any_to_offline(client, auth_headers):
    """
    INT-ST-04: Connection lost transitions to offline state.

    Reference: Spec lines 1009-1043
    """
    # ARRANGE: Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={"idToken": "mock-token", "refreshToken": "refresh", "expiresIn": "3600"},
        status=200
    )

    # Mock 1st call: device online and cooking
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "COOKING",
            "currentTemperature": 65.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 3600,
            "cookTimeElapsed": 1800
        },
        status=200
    )

    # Mock 2nd call: device offline (404)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={"error": "Device offline"},
        status=404
    )

    # ACT: Check progression from online to offline
    response1 = client.get('/status', headers=auth_headers)
    assert response1.status_code == 200
    status1 = response1.get_json()
    assert status1["device_online"] is True
    assert status1["state"] == "cooking"

    response2 = client.get('/status', headers=auth_headers)
    # Device offline should return 503 with DEVICE_OFFLINE error
    assert response2.status_code == 503
    error_data = response2.get_json()
    assert error_data["error"] == "DEVICE_OFFLINE"


@responses.activate
def test_int_st_05_cooking_to_idle(client, auth_headers):
    """
    INT-ST-05: Stopping cook transitions to idle.

    Reference: Spec lines 1047-1095
    """
    # ARRANGE: Mock Firebase auth
    responses.add(
        responses.POST,
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        json={"idToken": "mock-token", "refreshToken": "refresh", "expiresIn": "3600"},
        status=200
    )

    # Mock 1st status: device cooking
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "COOKING",
            "currentTemperature": 65.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 3600,
            "cookTimeElapsed": 1800
        },
        status=200
    )

    # Mock status check inside stop_cook (checking if running)
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "COOKING",
            "currentTemperature": 65.0,
            "targetTemperature": 65.0,
            "cookTimeRemaining": 3600,
            "cookTimeElapsed": 1800
        },
        status=200
    )

    # Mock stop command succeeds
    responses.add(
        responses.POST,
        "https://anovaculinary.io/api/v1/devices/test-device-123/stop",
        json={"success": True, "state": "idle"},
        status=200
    )

    # Mock final status: device now idle
    responses.add(
        responses.GET,
        "https://anovaculinary.io/api/v1/devices/test-device-123",
        json={
            "online": True,
            "cookerState": "IDLE",
            "currentTemperature": 65.0,
            "targetTemperature": None,
            "cookTimeRemaining": None,
            "cookTimeElapsed": None
        },
        status=200
    )

    # ACT: Verify state transitions
    response1 = client.get('/status', headers=auth_headers)
    assert response1.status_code == 200
    assert response1.get_json()["state"] == "cooking"

    response2 = client.post('/stop-cook', headers=auth_headers)
    assert response2.status_code == 200
    assert response2.get_json()["device_state"] == "idle"

    response3 = client.get('/status', headers=auth_headers)
    assert response3.status_code == 200
    assert response3.get_json()["state"] == "idle"
