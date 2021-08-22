## SX1276
MicroPython Library for SX1276 
## Features
* Send request for acknowledgement and wait 15 seconds for response.
* Send request but specify a wrong receiver id so acknowledgement will not succeed.
* Send broadcast and wait no time
## My dev environment
* Two Raspberry Pi Pico boards and two Adafruit RFM95W breakouts
* VScode with Pico-Go extension 
* I configured project and global settings <i>pico-go.json</i> for Pico-Go ext so I can open two VScode window/instances and connect to two Pico boards simultanously
## Usage
* Connect two boards to dev machine
* Open sender and receiver folders in two separate VScode windows.
* Upload lora.py to boards 
* Run sender.py and receiver.py
