#!/usr/bin/env python3
"""
Interactive demo runner for the Anova sous vide assistant.

Starts the simulator and Flask server, then runs a cooking demo
to showcase the complete workflow.

Usage:
    python -m demo.run_demo                    # Full demo (60x speed)
    python -m demo.run_demo --time-scale 600   # Faster (600x)
    python -m demo.run_demo --interactive      # Interactive mode
    python -m demo.run_demo --scenario chicken # Specific scenario
    python -m demo.run_demo --list             # List scenarios

Reference: Plan Phase 3 - Demo Script
"""

import argparse
import asyncio
import signal
import sys
import time

import requests

from demo.scenarios import CookScenario, get_scenario, print_scenarios

# Configuration
DEFAULT_TIME_SCALE = 60.0
DEFAULT_WS_PORT = 28765
DEFAULT_CONTROL_PORT = 28766
DEFAULT_FLASK_PORT = 28767


class DemoRunner:
    """
    Orchestrates the demo environment.

    Manages simulator, Flask server, and demo execution.
    """

    def __init__(
        self,
        time_scale: float = DEFAULT_TIME_SCALE,
        ws_port: int = DEFAULT_WS_PORT,
        control_port: int = DEFAULT_CONTROL_PORT,
        flask_port: int = DEFAULT_FLASK_PORT,
    ):
        self.time_scale = time_scale
        self.ws_port = ws_port
        self.control_port = control_port
        self.flask_port = flask_port

        self.simulator = None
        self.flask_process = None
        self._running = False

        # API endpoints
        self.api_base = f"http://localhost:{flask_port}"
        self.control_base = f"http://localhost:{control_port}"
        self.api_key = "demo-api-key-12345"

    async def start(self):
        """Start simulator and Flask server."""
        print("=" * 70)
        print("ANOVA SOUS VIDE DEMO")
        print("=" * 70)
        print()
        print(f"Time scale: {self.time_scale}x (1 minute = {60 / self.time_scale:.1f} seconds)")
        print()

        # Import here to avoid circular imports
        from simulator.config import Config as SimConfig
        from simulator.server import AnovaSimulator

        # Configure simulator
        sim_config = SimConfig(
            ws_port=self.ws_port,
            control_port=self.control_port,
            firebase_port=self.ws_port + 10,
            time_scale=self.time_scale,
            heating_rate=60.0,  # Fast heating for demo
            ambient_temp=22.0,
            valid_tokens=["demo-token"],
        )

        # Start simulator
        print("[SETUP] Starting Anova simulator...")
        self.simulator = AnovaSimulator(config=sim_config)
        await self.simulator.start(start_control=True)
        print(f"[SETUP] Simulator running on ws://localhost:{self.ws_port}")
        print(f"[SETUP] Control API on http://localhost:{self.control_port}")

        # Start Flask server in subprocess
        print("[SETUP] Starting Flask server...")
        await self._start_flask_server()
        print(f"[SETUP] Flask API on {self.api_base}")

        # Wait for services to be ready
        await self._wait_for_services()
        print("[SETUP] All services ready!")
        print()

        self._running = True

    async def _start_flask_server(self):
        """Start Flask server as subprocess."""
        import os
        import subprocess

        env = os.environ.copy()
        env["PERSONAL_ACCESS_TOKEN"] = "demo-token"
        env["API_KEY"] = self.api_key
        env["ANOVA_WEBSOCKET_URL"] = f"ws://localhost:{self.ws_port}"
        env["DEBUG"] = "false"

        # Start Flask in subprocess
        self.flask_process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"""
import sys
sys.path.insert(0, '.')
from flask import Flask
from server.config import Config
from server.anova_client import AnovaWebSocketClient
from server.middleware import register_error_handlers, setup_request_logging
from server.routes import api
import logging
logging.basicConfig(level=logging.WARNING)

config = Config(
    PERSONAL_ACCESS_TOKEN="demo-token",
    API_KEY="{self.api_key}",
    ANOVA_WEBSOCKET_URL="ws://localhost:{self.ws_port}",
    DEBUG=False,
)

app = Flask(__name__)
app.config["ANOVA_CONFIG"] = config
app.config["API_KEY"] = config.API_KEY
app.config["DEBUG"] = config.DEBUG

client = AnovaWebSocketClient(config)
app.config["ANOVA_CLIENT"] = client

app.register_blueprint(api)
register_error_handlers(app)
setup_request_logging(app)

app.run(host="127.0.0.1", port={self.flask_port}, debug=False, use_reloader=False)
""",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def _wait_for_services(self, timeout: float = 30.0):
        """Wait for all services to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                # Check Flask
                resp = requests.get(f"{self.api_base}/health", timeout=1)
                if resp.status_code == 200:
                    return
            except requests.exceptions.RequestException:
                pass
            await asyncio.sleep(0.5)

        raise TimeoutError("Services did not start in time")

    async def stop(self):
        """Stop all services."""
        print()
        print("[CLEANUP] Stopping services...")
        self._running = False

        if self.flask_process:
            self.flask_process.terminate()
            self.flask_process.wait(timeout=5)
            print("[CLEANUP] Flask server stopped")

        if self.simulator:
            await self.simulator.stop()
            print("[CLEANUP] Simulator stopped")

        print("[CLEANUP] Done!")

    def _api_headers(self) -> dict:
        """Get API headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _print_api_call(self, method: str, endpoint: str, data: dict | None = None):
        """Print API call info."""
        if data:
            import json

            print(f"[API] {method} {endpoint} {json.dumps(data)}")
        else:
            print(f"[API] {method} {endpoint}")

    def _print_api_response(self, response: requests.Response):
        """Print API response info."""
        import json

        try:
            data = response.json()
            print(f"[API] Response: {response.status_code} {json.dumps(data)}")
        except Exception:
            print(f"[API] Response: {response.status_code}")

    async def run_scenario(self, scenario: CookScenario):  # noqa: PLR0915
        """
        Run a complete cooking scenario.

        Args:
            scenario: The cooking scenario to run
        """
        print("=" * 70)
        print(f"DEMO: {scenario.name}")
        print("=" * 70)
        print()
        print(f"Description: {scenario.description}")
        print(f"Temperature: {scenario.temp_celsius}°C")
        print(f"Time: {scenario.time_minutes} minutes")
        print(f"Food: {scenario.food_type}")
        print()

        # Calculate actual duration with time scale
        actual_duration = scenario.time_minutes * 60 / self.time_scale
        print(
            f"(With {self.time_scale}x time scale, this will take ~{actual_duration:.0f} seconds)"
        )
        print()

        # 1. Start cook
        print("-" * 40)
        print("Starting cook...")
        start_data = {
            "temperature_celsius": scenario.temp_celsius,
            "time_minutes": scenario.time_minutes,
            "food_type": scenario.food_type,
        }
        self._print_api_call("POST", "/start-cook", start_data)

        response = requests.post(
            f"{self.api_base}/start-cook",
            headers=self._api_headers(),
            json=start_data,
        )
        self._print_api_response(response)

        if response.status_code != 200:
            print("[ERROR] Failed to start cook!")
            return

        print()

        # 2. Monitor progress
        print("-" * 40)
        print("Monitoring cook progress...")
        print()

        last_state = None
        while self._running:
            await asyncio.sleep(0.5)

            response = requests.get(
                f"{self.api_base}/status",
                headers=self._api_headers(),
            )

            if response.status_code != 200:
                print(f"[ERROR] Status check failed: {response.status_code}")
                break

            data = response.json()
            state = data["state"]
            current_temp = data["current_temp_celsius"]
            target_temp = data.get("target_temp_celsius")
            time_remaining = data.get("time_remaining_minutes")

            # Print status update
            if state == "preheating":
                print(f"[STATUS] Preheating... {current_temp:.1f}°C → {target_temp}°C")
            elif state == "cooking":
                if last_state != "cooking":
                    print("[STATUS] Reached target! Starting timer...")
                if time_remaining is not None:
                    print(
                        f"[STATUS] Cooking... Time remaining: {time_remaining} min | Temp: {current_temp:.1f}°C"
                    )
                else:
                    print(f"[STATUS] Cooking... Temp: {current_temp:.1f}°C")
            elif state == "done":
                print(f"[STATUS] Cook complete! Temperature held at {current_temp:.1f}°C")
                break
            elif state == "idle":
                print(f"[STATUS] Idle. Temp: {current_temp:.1f}°C")
                break

            last_state = state

        print()

        # 3. Stop cook (if not auto-stopped)
        print("-" * 40)
        print("Stopping cook...")
        self._print_api_call("POST", "/stop-cook")

        response = requests.post(
            f"{self.api_base}/stop-cook",
            headers=self._api_headers(),
        )
        self._print_api_response(response)

        print()
        print("=" * 70)
        print("Demo Complete!")
        print(f"Expected result: {scenario.expected_result}")
        print("=" * 70)

    async def interactive_mode(self):  # noqa: PLR0915
        """Run in interactive mode with user commands."""
        print("=" * 70)
        print("INTERACTIVE MODE")
        print("=" * 70)
        print()
        print("Commands:")
        print("  status     - Get current device status")
        print("  start      - Start a cook (prompts for parameters)")
        print("  stop       - Stop current cook")
        print("  scenarios  - List available scenarios")
        print("  run <name> - Run a scenario (e.g., 'run chicken')")
        print("  reset      - Reset simulator to initial state")
        print("  quit       - Exit demo")
        print()

        while self._running:
            try:
                cmd = input("demo> ").strip().lower()

                if not cmd:
                    continue

                if cmd in {"quit", "exit"}:
                    break

                elif cmd == "status":
                    response = requests.get(
                        f"{self.api_base}/status",
                        headers=self._api_headers(),
                    )
                    self._print_api_response(response)

                elif cmd == "stop":
                    response = requests.post(
                        f"{self.api_base}/stop-cook",
                        headers=self._api_headers(),
                    )
                    self._print_api_response(response)

                elif cmd == "start":
                    temp = float(input("  Temperature (°C): "))
                    time_min = int(input("  Time (minutes): "))
                    food = input("  Food type (optional): ").strip() or None

                    data = {"temperature_celsius": temp, "time_minutes": time_min}
                    if food:
                        data["food_type"] = food

                    response = requests.post(
                        f"{self.api_base}/start-cook",
                        headers=self._api_headers(),
                        json=data,
                    )
                    self._print_api_response(response)

                elif cmd == "scenarios":
                    print_scenarios()

                elif cmd.startswith("run "):
                    scenario_name = cmd[4:].strip()
                    try:
                        scenario = get_scenario(scenario_name)
                        await self.run_scenario(scenario)
                    except KeyError as e:
                        print(f"Error: {e}")

                elif cmd == "reset":
                    response = requests.post(f"{self.control_base}/reset")
                    print(f"Simulator reset: {response.json()}")

                else:
                    print(f"Unknown command: {cmd}")

            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                break
            except Exception as e:
                print(f"Error: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Anova Sous Vide Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m demo.run_demo                    # Run quick demo (60x speed)
  python -m demo.run_demo --scenario chicken # Run chicken scenario
  python -m demo.run_demo --time-scale 600   # 10x faster
  python -m demo.run_demo --interactive      # Interactive mode
  python -m demo.run_demo --list             # List scenarios
""",
    )
    parser.add_argument(
        "--scenario",
        "-s",
        default="quick",
        help="Scenario to run (default: quick)",
    )
    parser.add_argument(
        "--time-scale",
        "-t",
        type=float,
        default=DEFAULT_TIME_SCALE,
        help=f"Time acceleration factor (default: {DEFAULT_TIME_SCALE})",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available scenarios",
    )

    args = parser.parse_args()

    # Just list scenarios and exit
    if args.list:
        print_scenarios()
        return

    # Create runner
    runner = DemoRunner(time_scale=args.time_scale)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def shutdown():
        print("\n[SIGNAL] Shutdown requested...")
        runner._running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        # Start services
        await runner.start()

        if args.interactive:
            # Interactive mode
            await runner.interactive_mode()
        else:
            # Run specific scenario
            try:
                scenario = get_scenario(args.scenario)
                await runner.run_scenario(scenario)
            except KeyError as e:
                print(f"Error: {e}")
                print_scenarios()

    finally:
        await runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
