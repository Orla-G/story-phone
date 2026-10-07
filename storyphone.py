#!/usr/bin/env python3
"""
Story Phone - unattended story recording booth for a Raspberry Pi.

Flow:
  1. Handset is lifted (hook switch opens)  -> short pause, then a prompt plays
  2. Prompt finishes                        -> recording starts (red LED on)
  3. Handset is hung up                     -> recording stops and is saved

Prompts are played in order (round-robin) and each prompt keeps its own
story counter, so files are named Prompt1_Story001.wav, Prompt1_Story002.wav,
Prompt2_Story001.wav, and so on. Counters survive reboots via state.json.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import RPi.GPIO as GPIO

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# GPIO pin numbers (BCM numbering, not physical pin numbers)
HOOK_PIN = 17       # hook switch -> GND
RED_LED_PIN = 27    # recording indicator
GREEN_LED_PIN = 22  # ready / idle indicator

# ALSA device for the USB audio adapter, in "plughw:<card>,<device>" form.
# Check your card number with:  cat /proc/asound/cards
# You can also override this without editing the file:
#   STORYPHONE_AUDIO_DEVICE="plughw:1,0" python3 storyphone.py
AUDIO_DEVICE = os.environ.get("STORYPHONE_AUDIO_DEVICE", "plughw:3,0")

# Everything lives next to this script, so the project can be cloned anywhere.
BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
RECORDINGS_DIR = BASE_DIR / "recordings"
STATE_FILE = BASE_DIR / "state.json"

MIN_RECORDING_SECONDS = 1.0   # recordings shorter than this are discarded
DEBOUNCE_SECONDS = 0.2        # ignore switch bounce
PICKUP_DELAY_SECONDS = 0.3    # pause between pickup and the prompt starting

# Which GPIO reading means "handset is resting on the hook".
# With the switch wired between the pin and GND and the internal pull-up
# enabled, a switch that is OPEN when the handset is down reads HIGH.
# If your phone behaves the opposite way, change this to GPIO.LOW.
ON_HOOK_VALUE = GPIO.HIGH


# ---------------------------------------------------------------------------
# Prompts and state
# ---------------------------------------------------------------------------

def find_prompts():
    """Return all .wav files in the prompts folder, sorted by file name.

    Name them so they sort in the order you want them played, e.g.
    Prompt1.wav, Prompt2.wav ... (use Prompt01.wav if you have more than 9).
    """
    return sorted(PROMPTS_DIR.glob("*.wav"))


def load_state(prompt_count):
    """Load the saved prompt position and per-prompt story counts."""
    saved = {}
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("Could not read state file, starting fresh.")

    # Pad or trim the counts so they always match the number of prompts.
    counts = list(saved.get("story_counts", []))
    counts = (counts + [0] * prompt_count)[:prompt_count]

    index = saved.get("current_prompt_index", 0)
    if not 0 <= index < prompt_count:
        index = 0

    return {"current_prompt_index": index, "story_counts": counts}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# ---------------------------------------------------------------------------
# Hardware helpers
# ---------------------------------------------------------------------------

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(HOOK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(RED_LED_PIN, GPIO.OUT)
    GPIO.setup(GREEN_LED_PIN, GPIO.OUT)


def is_on_hook():
    return GPIO.input(HOOK_PIN) == ON_HOOK_VALUE


def set_idle_lights():
    GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
    GPIO.output(RED_LED_PIN, GPIO.LOW)


def set_recording_lights():
    GPIO.output(GREEN_LED_PIN, GPIO.LOW)
    GPIO.output(RED_LED_PIN, GPIO.HIGH)


def startup_blink():
    """Alternate red/green a few times so you can see the program started."""
    for _ in range(3):
        GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)
        GPIO.output(RED_LED_PIN, GPIO.HIGH)
        time.sleep(0.2)
    GPIO.output(RED_LED_PIN, GPIO.LOW)


def blink_confirm():
    """Three red blinks after a recording is saved successfully."""
    for _ in range(3):
        GPIO.output(RED_LED_PIN, GPIO.HIGH)
        time.sleep(0.15)
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        time.sleep(0.15)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def play_prompt(prompt_path):
    """Play a prompt. Returns True if it finished, False if the caller hung up.

    aplay runs in the background so we can keep watching the hook switch and
    stop playback immediately if the handset is put back.
    """
    proc = subprocess.Popen(["aplay", "-D", AUDIO_DEVICE, str(prompt_path)])

    while proc.poll() is None:  # still playing
        if is_on_hook():
            proc.terminate()
            proc.wait()
            return False
        time.sleep(0.05)

    return True


def start_recording(output_path):
    return subprocess.Popen([
        "arecord",
        "-D", AUDIO_DEVICE,
        "-c", "1",
        "-r", "44100",
        "-f", "S16_LE",
        str(output_path),
    ])


def stop_recording(process):
    process.terminate()
    process.wait()


def next_output_path(state, prompt_count):
    idx = state["current_prompt_index"]
    prompt_number = idx + 1  # 1-based in file names
    story_number = state["story_counts"][idx] + 1
    filename = f"Prompt{prompt_number}_Story{story_number:03d}.wav"
    return RECORDINGS_DIR / filename, idx, story_number


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    prompt_files = find_prompts()
    if not prompt_files:
        print(f"No .wav prompt files found in {PROMPTS_DIR}")
        sys.exit(1)

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state(len(prompt_files))

    setup_gpio()
    startup_blink()
    set_idle_lights()
    print(f"Story Phone ready with {len(prompt_files)} prompt(s). "
          "Waiting for pickup...")

    try:
        while True:
            # Wait for pickup (off-hook)
            while is_on_hook():
                time.sleep(0.05)

            time.sleep(DEBOUNCE_SECONDS)
            if is_on_hook():
                continue  # false trigger, bounced back

            print("Phone picked up.")
            time.sleep(PICKUP_DELAY_SECONDS)

            prompt_path = prompt_files[state["current_prompt_index"]]
            finished_naturally = play_prompt(prompt_path)

            if not finished_naturally:
                print("Hung up during prompt, skipping recording.")
                set_idle_lights()
                continue

            output_path, prompt_idx, story_number = next_output_path(
                state, len(prompt_files)
            )
            set_recording_lights()
            print(f"Recording to {output_path}")
            record_start = time.time()
            proc = start_recording(output_path)

            # Wait for hang-up
            while not is_on_hook():
                time.sleep(0.05)

            time.sleep(DEBOUNCE_SECONDS)
            stop_recording(proc)
            duration = time.time() - record_start

            if duration < MIN_RECORDING_SECONDS:
                print("Recording too short, discarding.")
                output_path.unlink(missing_ok=True)
            else:
                print(f"Saved {output_path} ({duration:.1f}s)")
                state["story_counts"][prompt_idx] = story_number
                state["current_prompt_index"] = (
                    (prompt_idx + 1) % len(prompt_files)
                )
                save_state(state)
                blink_confirm()

            set_idle_lights()
            print("Idle. Waiting for next pickup...")

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
