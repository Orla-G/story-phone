#!/usr/bin/env python3
"""
Story Phone hardware test.

A small menu for checking the hook switch and both LEDs on their own,
before running the full storyphone.py program.

Keep the pin numbers and ON_HOOK_VALUE the same as in storyphone.py.
"""

import time

import RPi.GPIO as GPIO

# ---------- Configuration (match storyphone.py) ----------

HOOK_PIN = 17
RED_LED_PIN = 27
GREEN_LED_PIN = 22

# Switch open when the handset is down + internal pull-up = reads HIGH.
# If the on-hook / off-hook labels come out backwards, change to GPIO.LOW.
ON_HOOK_VALUE = GPIO.HIGH

# ---------- Setup ----------

GPIO.setmode(GPIO.BCM)
GPIO.setup(HOOK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RED_LED_PIN, GPIO.OUT)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT)
GPIO.output(RED_LED_PIN, GPIO.LOW)
GPIO.output(GREEN_LED_PIN, GPIO.LOW)


def is_on_hook():
    return GPIO.input(HOOK_PIN) == ON_HOOK_VALUE


def test_hook_switch():
    print("\n--- Hook Switch Test ---")
    print("Lift and replace the handset to see state changes.")
    print("Press Ctrl+C to return to the menu.\n")

    last_state = is_on_hook()
    print(f"Current state: {'ON-HOOK (hung up)' if last_state else 'OFF-HOOK (picked up)'}")

    try:
        while True:
            current_state = is_on_hook()
            if current_state != last_state:
                label = "ON-HOOK (hung up)" if current_state else "OFF-HOOK (picked up)"
                print(f"State changed -> {label}")
                last_state = current_state
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nReturning to menu.")


def flash_led(pin, count):
    for _ in range(count):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.3)


def test_led(pin, color_name):
    print(f"\n--- {color_name} LED Test ---")
    while True:
        user_input = input(
            f"Enter number of times to flash {color_name} LED (or 'b' to go back): "
        ).strip()
        if user_input.lower() == "b":
            return
        if not user_input.isdigit():
            print("Please enter a valid number.")
            continue
        count = int(user_input)
        if count <= 0:
            print("Please enter a number greater than 0.")
            continue
        print(f"Flashing {color_name} LED {count} time(s)...")
        flash_led(pin, count)
        print("Done.")


def main_menu():
    while True:
        print("\n===== Story Phone Hardware Test =====")
        print("1. Test pick up/hang up (hook switch)")
        print("2. Test Green LED")
        print("3. Test Red LED")
        print("4. Exit")
        choice = input("Select an option: ").strip()

        if choice == "1":
            test_hook_switch()
        elif choice == "2":
            test_led(GREEN_LED_PIN, "Green")
        elif choice == "3":
            test_led(RED_LED_PIN, "Red")
        elif choice == "4":
            print("Exiting.")
            break
        else:
            print("Invalid choice, try again.")


if __name__ == "__main__":
    try:
        main_menu()
    finally:
        GPIO.cleanup()
