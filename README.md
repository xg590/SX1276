## SX1276
MicroPython Library for SX1276 
## Features
* Send request for acknowledgement and wait 15 seconds for response.
* Send request but specify a wrong receiver id so acknowledgement will not succeed.
* Send broadcast and wait no time
## My dev environment
* Two Raspberry Pi Pico boards and two Adafruit RFM95W breakouts
* VScode with Pico-Go extension 
* I configured project and global settings for Pico-Go ext so I can open two VScode instances and connect to two Pico boards simultanously
## Usage
* Upload lora.py to board 
* Run sender.py and receiver.py
