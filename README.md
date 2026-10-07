# story-phone

To facilitate collecting stories for an event I built what I am calling a "Story Phone". The project uses a Raspberry Pi 3 B+ inside the housing of a 1970s phone to play prompts and record responses.

When someone lifts the handset, a prompt plays. When it finishes, whatever they say is recorded until they hang up. It runs unattended, starts automatically on boot, and keeps its story counters across restarts, so it can sit in a booth all day without anyone babysitting it.

> **A note on how this was made:** Claude (an AI assistant from Anthropic) was used in the creation of the code and documentation in this repository. Everything was checked by a human prior to implementation, and the hardware was built and tested by hand.

## How it works

1. **Idle** – green LED on, waiting for the handset to be lifted.
2. **Pickup** – after a short pause (300 ms) the next prompt plays through the handset speaker. If the caller hangs up during the prompt, playback stops immediately and nothing is recorded.
3. **Recording** – red LED on while the caller's response is recorded from the handset microphone.
4. **Hang up** – the recording is saved, the red LED blinks three times to confirm, and the phone returns to idle. Recordings shorter than one second are discarded.

Prompts play in order and loop. Each prompt has its own story counter, so recordings are named like this:

```
Prompt1_Story001.wav
Prompt2_Story001.wav
Prompt3_Story001.wav
Prompt1_Story002.wav
...
```

When the program starts, the LEDs alternate red/green three times so you can tell it booted and is ready.

## Hardware

- Raspberry Pi 3 B+ (other Pi models with GPIO and a USB port should work, but this is untested)
- microSD card (32 GB is plenty; a reputable Class 10 / A1 card is recommended)
- A phone handset or housing with an accessible mic, speaker and hook switch
- USB audio adapter with separate mic-in and headphone-out
- 1 red LED and 1 green LED
- 2 resistors, 220–330 ohm (one per LED)
- Jumper wires, breadboard or perfboard

The Pi's built-in 3.5 mm jack is output only, so a USB audio adapter is required for the microphone.

### Wiring

| Part | Pi GPIO (BCM) | Physical pin | Notes |
|------|---------------|--------------|-------|
| Hook switch | GPIO 17 | 11 | Other side of the switch goes to GND (pin 9) |
| Red LED (recording) | GPIO 27 | 13 | Through a resistor, cathode to GND (pin 14) |
| Green LED (ready) | GPIO 22 | 15 | Through a resistor, cathode to GND (pin 14) |

```
GPIO17 (pin 11) ----> Hook switch ----> GND (pin 9)
GPIO27 (pin 13) --[resistor]--> Red LED   --> GND (pin 14)
GPIO22 (pin 15) --[resistor]--> Green LED --> GND (pin 14)
USB port ----------> USB audio adapter ----> handset mic + speaker
```

The hook switch uses the Pi's internal pull-up resistor, so no external resistor is needed. The program assumes the switch is **open** when the handset is resting on the hook. If your phone is wired the opposite way, change `ON_HOOK_VALUE` to `GPIO.LOW` in both `storyphone.py` and `hardware_test.py`.

Pin numbers are set at the top of both scripts if you want to use different pins.

## Software setup

### 1. Flash Raspberry Pi OS

Use Raspberry Pi Imager and choose **Raspberry Pi OS Lite (64-bit)**. In the advanced options, set a hostname, enable SSH, add your Wi-Fi details if needed, and set your locale and time zone. Then boot the Pi and connect over SSH:

```bash
ssh <user>@<pi-hostname-or-ip>
```

### 2. Install dependencies

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git alsa-utils python3-rpi.gpio
```

`aplay` and `arecord` (from `alsa-utils`) handle all audio, and `python3-rpi.gpio` handles the switch and LEDs. There are no pip packages to install.

### 3. Get the code

```bash
git clone https://github.com/<your-username>/story-phone.git
cd story-phone
mkdir -p prompts
```

### 4. Set up the USB audio adapter

Plug in the adapter and list the sound cards:

```bash
cat /proc/asound/cards
```

The USB card's number can change between boots because the Pi has onboard audio and HDMI audio devices too. To pin the USB adapter to a fixed card number, create a config file:

```bash
sudo nano /etc/modprobe.d/alsa-base.conf
```

Add this line (index 3 stays clear of the onboard devices, which use 0 and 1):

```
options snd-usb-audio index=3
```

Save, reboot, and confirm the USB card shows up as card 3:

```bash
sudo reboot
cat /proc/asound/cards
```

The scripts default to `plughw:3,0`. If your card ends up with a different number, change `AUDIO_DEVICE` at the top of `storyphone.py`, or set it for a single run:

```bash
STORYPHONE_AUDIO_DEVICE="plughw:1,0" python3 storyphone.py
```

Test the microphone and speaker with the handset wired up:

```bash
arecord -D plughw:3,0 -c 1 -r 44100 -f S16_LE -d 5 test.wav
aplay -D plughw:3,0 test.wav
```

### 5. Add your prompts

Put your prompt files in the `prompts/` folder. They should be WAV files (16-bit PCM, mono, 44.1 kHz). The program plays every `.wav` in that folder in alphabetical order, so name them so they sort the way you want, for example `Prompt1.wav`, `Prompt2.wav`, and so on. Use zero-padded numbers (`Prompt01.wav`) if you have more than nine.

To copy files from your computer to the Pi:

```bash
scp Prompt1.wav Prompt2.wav Prompt3.wav Prompt4.wav <user>@<pi-hostname-or-ip>:~/story-phone/prompts/
```

If a file isn't in the right format, convert it with ffmpeg:

```bash
ffmpeg -i input.wav -ac 1 -ar 44100 -sample_fmt s16 Prompt1.wav
```

### 6. Test the hardware

`hardware_test.py` is a small menu for checking the hook switch and each LED by themselves:

```bash
python3 hardware_test.py
```

Try the hook switch test first. If "picked up" and "hung up" are backwards, flip `ON_HOOK_VALUE` as described in the wiring section.

### 7. Run it

```bash
python3 storyphone.py
```

Lift the handset, listen to the prompt, say something, and hang up. You should see the recording appear in `recordings/`. Press Ctrl+C to stop.

### 8. Start automatically on boot

Edit `storyphone.service` and replace `YOUR_USER` with your Linux username (and adjust the paths if the project isn't in your home directory). Then install it:

```bash
sudo cp storyphone.service /etc/systemd/system/storyphone.service
sudo systemctl daemon-reload
sudo systemctl enable storyphone.service
sudo systemctl start storyphone.service
```

Check that it's running:

```bash
sudo systemctl status storyphone.service
```

Watch the live log:

```bash
sudo journalctl -u storyphone.service -f
```

After editing the code later, apply the changes with:

```bash
sudo systemctl restart storyphone.service
```

Finally, reboot once and confirm the LEDs blink and the phone works without you logging in.

## A Note on Prompt Audio Files and Recording Names

Recordings are always saved as `Prompt<N>_Story<XXX>.wav`, where:

- `<N>` is the prompt's **position** in the list, starting at 1. It is *not* taken from the prompt's file name.
- `<XXX>` is a three-digit story counter that counts up separately for each prompt (`001`, `002`, `003`, ...).

When the program starts, it collects every `.wav` file in `prompts/`, sorts them alphabetically by file name, and numbers them 1, 2, 3, and so on. That number is what ends up in the recording's name. Because the name comes from the position, your prompt files can be called anything you like, and the recordings will still be named `Prompt1_...`, `Prompt2_...`.

For example, if `prompts/` contains these files:

- `Childhood.wav`
- `Favorite_Place.wav`
- `Advice.wav`

When the files are loaded they are sorted alphabetically, so `Advice.wav` will be associated with the `Prompt1_StoryXXX.wav` recordings, `Childhood.wav` with `Prompt2_StoryXXX.wav`, and `Favorite_Place.wav` with `Prompt3_StoryXXX.wav`:

| Sorted position | Prompt file | Recordings saved as |
|-----------------|-------------|---------------------|
| 1 | `Advice.wav` | `Prompt1_Story001.wav`, ... |
| 2 | `Childhood.wav` | `Prompt2_Story001.wav`, ... |
| 3 | `Favorite_Place.wav` | `Prompt3_Story001.wav`, ... |

A few things to keep in mind:

- **Keep a record of which prompt is which.** Since the recording names don't contain the prompt's file name, write down which prompt file matches each `Prompt<N>` number before the event. Printing the sorted list is an easy way to check:

  ```bash
  ls prompts/*.wav
  ```

- **To control the order, name the files so they sort the way you want.** Names like `Prompt1.wav`, `Prompt2.wav`, `Prompt3.wav` (or `01_Intro.wav`, `02_Childhood.wav`, ...) make the order obvious. Use zero-padded numbers if you have more than nine prompts, because `Prompt10.wav` sorts before `Prompt2.wav`.
- **Don't add, remove or rename prompt files once recording has started.** Doing so can change the sorted positions, so the same `Prompt<N>` number would refer to a different prompt, and the counters in `state.json` would no longer line up with the right prompts. If you need to change the prompts, finish or back up your current recordings first, then delete `state.json` to start numbering over.
- **Restart after changing prompts.** The list of prompts is read once when the program starts, so restart it (or the service) after making changes:

  ```bash
  sudo systemctl restart storyphone.service
  ```

## Collecting the recordings

Recordings are saved in the `recordings/` folder inside the project. To copy them to your computer over the local network (no internet needed, just a shared network or an ethernet cable between the two devices):

```bash
rsync -avz <user>@<pi-hostname-or-ip>:~/story-phone/recordings/ ./recordings/
```

`rsync` only transfers new or changed files, so it is quick to run repeatedly during an event. If you don't have `rsync`, `scp -r` works too:

```bash
scp -r <user>@<pi-hostname-or-ip>:~/story-phone/recordings ./
```

## Configuration

These settings are near the top of `storyphone.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `HOOK_PIN`, `RED_LED_PIN`, `GREEN_LED_PIN` | 17, 27, 22 | GPIO pins (BCM numbering) |
| `AUDIO_DEVICE` | `plughw:3,0` | ALSA device for the USB adapter |
| `MIN_RECORDING_SECONDS` | 1.0 | Shorter recordings are discarded |
| `DEBOUNCE_SECONDS` | 0.2 | Ignores switch bounce |
| `PICKUP_DELAY_SECONDS` | 0.3 | Pause between pickup and the prompt |
| `ON_HOOK_VALUE` | `GPIO.HIGH` | Pin reading when the handset is resting |

Prompt position and story counters are stored in `state.json` (created automatically). Delete it to start numbering over.

## Troubleshooting

**`aplay: audio open error` or `arecord: audio open error`** – The USB audio card isn't at the number the script expects. Run `cat /proc/asound/cards`, confirm the USB card is listed, and make sure `AUDIO_DEVICE` matches. Note that the program keeps running when audio fails, so check that recordings aren't empty before an event.

**USB card missing after changing the modprobe index** – A fixed index that collides with an onboard device (0 or 1) can stop the USB driver from loading. Use a higher index such as 3.

**Pick up and hang up are reversed** – Change `ON_HOOK_VALUE` between `GPIO.HIGH` and `GPIO.LOW` in both scripts.

**Nothing happens when the program starts** – Make sure at least one `.wav` file is in `prompts/`. The program exits with a message if the folder is empty.

**Pi won't show up on the network** – Give first boot a few minutes, check your router's device list, or connect over ethernet.

**Red power LED flickers** – The power supply is likely too weak. Use a proper 2.5 A supply.

## License

This project is released under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.
